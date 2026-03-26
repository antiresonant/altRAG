/*
 * scan.c — altRAG Pointer Skeleton Generator
 *
 * Scans skill files and builds a hierarchical pointer tree (.skt)
 * mapping byte offsets and line numbers to structural headings.
 *
 * Recognized structures:
 *   - Markdown headings (# through ######)
 *   - Bold headings (**Title** as standalone line)
 *   - Horizontal rules (---, ***, ___) as section breaks
 *   - YAML front matter (skipped)
 *
 * Usage: scan <file1.md> [file2.md ...] > output.skt
 *
 * Build: cc -O2 -o scan scan.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* portability: strdup is POSIX, not C99 — MSVC uses _strdup */
#ifdef _MSC_VER
#define strdup _strdup
#endif

#define MAX_SECTIONS 8192

typedef struct {
    int  depth;                /* heading level 1-6 */
    long offset;               /* byte offset from file start (true pointer) */
    long length;               /* byte length of section including children */
    int  line;                 /* 1-indexed line number */
    int  line_count;           /* lines in section including children */
    char *title;               /* heading text, stripped of markers (dynamically allocated) */
} Section;

/* ── Format detection ── */
typedef enum { FMT_AUTO, FMT_MD, FMT_YAML } Format;

static Format detect_format(const char *path) {
    const char *dot = strrchr(path, '.');
    if (!dot) return FMT_MD;
    if (strcmp(dot, ".yaml") == 0 || strcmp(dot, ".yml") == 0) return FMT_YAML;
    return FMT_MD;
}

/* ── Utility: trim trailing whitespace/CR from a length ── */
static int trim_right(const char *s, int len) {
    while (len > 0 && (s[len - 1] == ' '  || s[len - 1] == '\t' ||
                       s[len - 1] == '\r' || s[len - 1] == '\n'))
        len--;
    return len;
}

/* ── Detect horizontal rule: 3+ of same char (- * _) with optional spaces ── */
static int is_hrule(const char *s, int len) {
    char ch = 0;
    int  count = 0;
    for (int i = 0; i < len; i++) {
        char c = s[i];
        if (c == '\n' || c == '\r') break;
        if (c == ' '  || c == '\t') continue;
        if (ch == 0) {
            if (c == '-' || c == '*' || c == '_') { ch = c; count = 1; }
            else return 0;
        } else {
            if (c == ch) count++;
            else return 0;
        }
    }
    return count >= 3;
}

/* ── Detect standalone bold heading: **Title** on its own line ── */
static int is_bold_heading(const char *s, int len, char *out, int out_size) {
    /* skip leading whitespace (max 3 spaces, else it's a code block) */
    int start = 0;
    while (start < len && start < 3 && s[start] == ' ') start++;

    int rlen = len - start;
    const char *p = s + start;

    if (rlen < 5 || p[0] != '*' || p[1] != '*') return 0;

    /* find closing ** */
    for (int i = 2; i < rlen - 1; i++) {
        if (p[i] == '*' && p[i + 1] == '*') {
            /* rest of line must be whitespace */
            int j = i + 2;
            while (j < rlen && (p[j] == ' ' || p[j] == '\t' ||
                                p[j] == '\r' || p[j] == '\n'))
                j++;
            if (j < rlen) return 0; /* trailing non-whitespace */

            int tlen = i - 2;
            if (tlen <= 0) return 0;
            if (tlen >= out_size) tlen = out_size - 1;
            memcpy(out, p + 2, tlen);
            out[tlen] = '\0';
            return 1;
        }
    }
    return 0;
}

/* ── Skip YAML front matter (--- ... ---) at file start ── */
static long skip_front_matter(const char *buf, long fsize) {
    if (fsize < 3) return 0;
    if (buf[0] != '-' || buf[1] != '-' || buf[2] != '-') return 0;

    /* verify rest of first line is whitespace */
    long i = 3;
    while (i < fsize && buf[i] != '\n') {
        if (buf[i] != ' ' && buf[i] != '\t' && buf[i] != '\r') return 0;
        i++;
    }
    if (i >= fsize) return 0;
    i++; /* skip newline */

    /* find closing --- */
    while (i < fsize) {
        if (buf[i] == '-' && i + 2 < fsize && buf[i + 1] == '-' && buf[i + 2] == '-') {
            /* advance past closing --- line */
            i += 3;
            while (i < fsize && buf[i] != '\n') i++;
            if (i < fsize) i++; /* skip newline */
            return i;
        }
        /* advance to next line */
        while (i < fsize && buf[i] != '\n') i++;
        if (i < fsize) i++;
    }
    return 0; /* no closing --- found, don't skip anything */
}

/* ── Core scanner: extract structural sections from a file ── */
static int scan_file(const char *path, Section *secs, int max_sec,
                     int *out_total_lines) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "scan: cannot open: %s\n", path); return 0; }

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fsize == 0) { fclose(f); return 0; }

    char *buf = (char *)malloc(fsize + 1);
    if (!buf) { fclose(f); return 0; }
    fsize = (long)fread(buf, 1, fsize, f);
    buf[fsize] = '\0';
    fclose(f);

    /* skip YAML front matter if present */
    long data_start = skip_front_matter(buf, fsize);
    int  start_line = 1;
    if (data_start > 0) {
        for (long k = 0; k < data_start; k++)
            if (buf[k] == '\n') start_line++;
    }

    int  count      = 0;
    int  line       = start_line;
    int  in_code    = 0;
    int  anchor     = 0;  /* depth of last MD heading — bold/HR derive from this */
    long pos        = data_start;

    while (pos < fsize && count < max_sec) {
        /* find current line boundaries */
        long ls = pos;                              /* line start offset */
        long le = pos;                              /* line end offset   */
        while (le < fsize && buf[le] != '\n') le++;
        int  llen = (int)(le - ls);
        char *lp  = buf + ls;

        /* ── code block toggle ── */
        if (llen >= 3 &&
            ((lp[0] == '`' && lp[1] == '`' && lp[2] == '`') ||
             (lp[0] == '~' && lp[1] == '~' && lp[2] == '~'))) {
            in_code = !in_code;
            goto next;
        }
        if (in_code) goto next;

        /* ── markdown heading ── */
        if (lp[0] == '#') {
            int d = 0;
            while (d < llen && lp[d] == '#') d++;
            if (d >= 1 && d <= 6 && d < llen && lp[d] == ' ') {
                secs[count].depth  = d;
                secs[count].offset = ls;
                secs[count].line   = line;

                int ts  = d + 1;
                int tl  = trim_right(lp + ts, llen - ts);
                secs[count].title = (char *)malloc(tl + 1);
                memcpy(secs[count].title, lp + ts, tl);
                secs[count].title[tl] = '\0';

                anchor = d;
                count++;
                goto next;
            }
        }

        /* ── bold heading: always one level below the anchor ── */
        {
            char btitle[4096];
            if (is_bold_heading(lp, llen, btitle, sizeof(btitle))) {
                int d = (anchor > 0 && anchor < 6)
                        ? anchor + 1 : (anchor >= 6 ? 6 : 1);
                secs[count].depth  = d;
                secs[count].offset = ls;
                secs[count].line   = line;
                secs[count].title  = strdup(btitle);
                /* anchor NOT updated — bold headings are children, not new anchors */
                count++;
                goto next;
            }
        }

        /* ── horizontal rule: break at anchor level ── */
        if (llen >= 3 && is_hrule(lp, llen)) {
            int d = anchor > 0 ? anchor : 1;
            secs[count].depth  = d;
            secs[count].offset = ls;
            secs[count].line   = line;
            secs[count].title  = strdup("---");
            count++;
            /* don't update last_depth — HR is a break, not a new level */
            goto next;
        }

    next:
        pos = le + 1;
        line++;
    }

    *out_total_lines = line - 1;

    /* ── calculate section bounds ── */
    for (int i = 0; i < count; i++) {
        long end_off = fsize;
        int  end_ln  = *out_total_lines + 1;

        for (int j = i + 1; j < count; j++) {
            if (secs[j].depth <= secs[i].depth) {
                end_off = secs[j].offset;
                end_ln  = secs[j].line;
                break;
            }
        }
        secs[i].length     = end_off - secs[i].offset;
        secs[i].line_count = end_ln  - secs[i].line;
    }

    free(buf);
    return count;
}

/* ── YAML scanner: indentation depth → heading levels ── */
static int scan_yaml(const char *path, Section *secs, int max_sec,
                     int *out_total_lines) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "scan: cannot open: %s\n", path); return 0; }

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (fsize == 0) { fclose(f); return 0; }

    char *buf = (char *)malloc(fsize + 1);
    if (!buf) { fclose(f); return 0; }
    fsize = (long)fread(buf, 1, fsize, f);
    buf[fsize] = '\0';
    fclose(f);

    int  count          = 0;
    int  line           = 1;
    int  indent_unit    = 2;   /* auto-detected from first indent */
    int  indent_found   = 0;
    long pos            = 0;

    /* skip leading --- if present (YAML doc start) */
    if (fsize >= 3 && buf[0] == '-' && buf[1] == '-' && buf[2] == '-') {
        while (pos < fsize && buf[pos] != '\n') pos++;
        if (pos < fsize) pos++;
        line++;
    }

    while (pos < fsize && count < max_sec) {
        long ls  = pos;
        long le  = pos;
        while (le < fsize && buf[le] != '\n') le++;
        int llen = (int)(le - ls);
        char *lp = buf + ls;

        /* count leading spaces */
        int spaces = 0;
        while (spaces < llen && lp[spaces] == ' ') spaces++;

        /* skip empty, comment, and list-item lines */
        if (spaces >= llen || lp[spaces] == '#' || lp[spaces] == '\n' ||
            lp[spaces] == '\r' || (lp[spaces] == '-' && spaces + 1 < llen &&
            (lp[spaces + 1] == ' ' || lp[spaces + 1] == '\n'))) {
            goto next_yaml;
        }

        /* auto-detect indent unit from first indented line */
        if (!indent_found && spaces > 0) {
            indent_unit = spaces;
            indent_found = 1;
        }

        /* look for key: pattern */
        {
            int ks = spaces;
            int ke = ks;
            while (ke < llen && lp[ke] != ':' && lp[ke] != '\n' && lp[ke] != '\r')
                ke++;

            if (ke < llen && lp[ke] == ':') {
                int depth = (indent_unit > 0) ? spaces / indent_unit + 1 : 1;
                int tlen  = ke - ks;
                tlen = trim_right(lp + ks, tlen);
                if (tlen > 0) {
                    secs[count].depth  = depth;
                    secs[count].offset = ls;
                    secs[count].line   = line;
                    secs[count].title  = (char *)malloc(tlen + 1);
                    memcpy(secs[count].title, lp + ks, tlen);
                    secs[count].title[tlen] = '\0';
                    count++;
                }
            }
        }

    next_yaml:
        pos = le + 1;
        line++;
    }

    *out_total_lines = line - 1;

    /* calculate section bounds */
    for (int i = 0; i < count; i++) {
        long end_off = fsize;
        int  end_ln  = *out_total_lines + 1;
        for (int j = i + 1; j < count; j++) {
            if (secs[j].depth <= secs[i].depth) {
                end_off = secs[j].offset;
                end_ln  = secs[j].line;
                break;
            }
        }
        secs[i].length     = end_off - secs[i].offset;
        secs[i].line_count = end_ln  - secs[i].line;
    }

    free(buf);
    return count;
}

/* ── Emit .skt file header ── */
static void emit_header(FILE *out) {
    fprintf(out, "# altRAG Pointer Skeleton\n");
    fprintf(out, "# d\toff\tlen\tln\tlc\ttitle\n");
}

/* ── Emit sections for one file ── */
static void emit_skt(const char *path, Section *secs, int count, FILE *out) {
    fprintf(out, "\n@ %s\n", path);
    for (int i = 0; i < count; i++) {
        fprintf(out, "%d\t%ld\t%ld\t%d\t%d\t%s\n",
                secs[i].depth,
                secs[i].offset,
                secs[i].length,
                secs[i].line,
                secs[i].line_count,
                secs[i].title);
    }
}

/* ── Free dynamically allocated titles in sections array ── */
static void free_section_titles(Section *secs, int count) {
    for (int i = 0; i < count; i++) {
        free(secs[i].title);
        secs[i].title = NULL;
    }
}

/* ── Main ── */
int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr,
            "altRAG Skeleton Generator\n"
            "Usage: scan [--format md|yaml|auto] <file1> [file2 ...] [> output.skt]\n"
            "\n"
            "Scans skill files and emits a pointer skeleton (.skt)\n"
            "mapping byte offsets and line numbers to structural elements.\n"
            "\n"
            "Formats:\n"
            "  md   (default) Markdown headings, bold headings, horizontal rules\n"
            "  yaml           YAML keys with indentation-based depth\n"
            "  auto           Detect from file extension\n");
        return 1;
    }

    Section secs[MAX_SECTIONS];
    Format forced_fmt = FMT_AUTO;

    emit_header(stdout);

    for (int i = 1; i < argc; i++) {
        /* parse --format flag */
        if (strcmp(argv[i], "--format") == 0 && i + 1 < argc) {
            i++;
            if (strcmp(argv[i], "md") == 0)        forced_fmt = FMT_MD;
            else if (strcmp(argv[i], "yaml") == 0)  forced_fmt = FMT_YAML;
            else                                    forced_fmt = FMT_AUTO;
            continue;
        }

        Format fmt = (forced_fmt != FMT_AUTO) ? forced_fmt : detect_format(argv[i]);
        int total_lines = 0;
        int count;

        if (fmt == FMT_YAML)
            count = scan_yaml(argv[i], secs, MAX_SECTIONS, &total_lines);
        else
            count = scan_file(argv[i], secs, MAX_SECTIONS, &total_lines);

        if (count > 0) {
            emit_skt(argv[i], secs, count, stdout);
        } else if (count == 0) {
            fprintf(stderr, "scan: no structure found in: %s\n", argv[i]);
        }
        free_section_titles(secs, count);
    }

    return 0;
}
