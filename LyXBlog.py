import sys
import os
import shutil
import re
import subprocess
import datetime


def print_usage():
    print('LyXBlog [--update] <input file> <blog base dir> '
          '<assets relative dir>')


class FrontMatter:
    def __init__(self, front_matter):
        # Removes the eventual '%' symbols
        if front_matter[0] == '%':
            # removes the commenting '%'.
            self.front_matter = re.sub('^%', '', front_matter, flags=re.M)
        else:
            self.front_matter = front_matter

        # Extracts html_file_name
        m = re.match(r'html_file_name:\s*(.+)\s*$', self.front_matter,
                     flags=re.M)
        if m is None:
            raise Exception('The LyXBlog front matter must begin with '
                            '"html_file_name:"!')
        self.html_file_name = m[1]

        # Extracts the date
        m = re.search(r'^date:\s*(.+)\s*$', self.front_matter, flags=re.M)
        self.date = m[1]
        try:
            datetime.datetime.strptime(self.date, '%Y-%m-%d')
        except ValueError:
            raise Exception("Invalid date in front matter! Make sure you're "
                            "using the YYYY-MM-DD format.")

        # Removes the html_file_name line (it doesn't belong to the real
        # Jekyll front matter)
        pos = self.front_matter.find('\n') + 1
        self.front_matter = self.front_matter[pos:]

        if (not self.front_matter.startswith('---\n') or
                not self.front_matter.endswith('---\n')):
            raise Exception("The real front matter must start with '---'")


    @staticmethod
    def from_file(tex_path):
        with open(tex_path, encoding='utf-8') as f:
            found = False
            lines = []
            for line in f:
                if found:
                    if line.startswith('%LyXBlog-end'):
                        break
                    lines.append(line)
                elif line.startswith('%LyXBlog-start'):
                    found = True
            if not found:
                raise Exception('There is NO Front Matter in the file!')

            return FrontMatter(''.join(lines))


# When a LyX file is converted into a TeX file, the extensions of the image
# filenames are lost (e.g. picture.svg becomes picture).
def get_file_extensions(lyx_path):
    name_to_ext = {}
    with open(lyx_path, encoding='utf-8') as f:
        found = False
        for line in f:
            if found:
                if line.startswith('\end_inset'):
                    found = False
                else:
                    m = re.match(r'\s*filename\s+(\S+)\s*\Z', line)
                    if m:
                        fname = m[1]
                        path_ext = os.path.splitext(fname)
                        name_to_ext[path_ext[0]] = path_ext[1][1:]
                        found = False
            elif line.startswith(r'\begin_inset Graphics'):
                found = True
    return name_to_ext


def get_date_basename(path, date):
    return date + '-' + os.path.basename(path)


# TODO: proper html parsing or pandoc filter (generated on-the-fly?)
def handle_images(html, blog_path, assets_rel_dir, front_matter, name_to_ext,
                  update=True):
    """
    Copy the images into the assets directory and fix their path in `html`.
    """
    assets_rel_dir = os.path.normpath(assets_rel_dir)

    # The images are created in a directory of the form
    #   blog_path/assets_rel_dir/date-html_fname
    # so that images of different articles are in separate directories.
    date_html_fname = get_date_basename(front_matter.html_file_name,
                                        front_matter.date)
    rel_dest_dir = os.path.join(assets_rel_dir, date_html_fname)
    dest_dir = os.path.join(blog_path, rel_dest_dir)

    def replace_groups(match, new_texts):
        output = []
        num_groups = match.lastindex
        pos = 0
        for group, new_text in zip(range(1, num_groups + 1), new_texts):
            start = match.start(group) - match.start(0)
            end = match.end(group) - match.start(0)
            output.append(match[0][pos:start] + new_text)
            pos = end
        output.append(match[0][pos:])
        return ''.join(output)

    def fix(match):
        full_path = match[2]
        ext = name_to_ext.get(full_path, None)
        if ext:
            # Copy the image into dest_dir
            full_path += '.' + ext
            base_name = os.path.basename(full_path)
            dest_full_path = os.path.join(dest_dir, base_name)
            if not update and os.path.exists(dest_full_path):
                raise Exception('Already exists: ' + dest_full_path)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(full_path, dest_full_path)

            # Return the blog-relative path of the copied image
            path = ('/' + assets_rel_dir + '/' + date_html_fname + '/'
                    + base_name)

            # Extracts the desired width(%) of the image (if present)
            m = re.search(r'.*style="width:([^%]+)%".*', match[3])
            if m:
                margin = (100 - float(m[1])) / 2
                new_final_part = replace_groups(m, ['100'])
            else:
                margin = 0.0
                new_final_part = ' style="width=100%" ' + match[3]
            new_p = '<p style="margin: 1em {:.5}%">'.format(margin)

            return replace_groups(match, [new_p, path, new_final_part])

        return full_path            # no fixing

    html = re.sub(r'(<p>)<img src="([^"]*)"([^>]*)>', fix, html)
    return html


def get_math_env_pos(latex):
    def find_end(math_env, start):
        escaped_math_env = re.escape(math_env)      # escapes '*'
        search_re = r"\\begin{verbatim}|\\begin{%s}|\\end{%s}" % \
                    (escaped_math_env, escaped_math_env)
        begin_env = r"\begin{%s}" % math_env
        open_occ = 1
        while True:
            m = re.search(search_re, latex[start:])
            start += m.end(0)
            if m is None:
                raise Exception("Can't find closing \end{}")
            if m[0] == r"\begin{verbatim}":
                pos = latex[start:].find(r"\end{verbatim}")
                if pos == -1:
                    raise Exception("Can't find closing \end{verbatim}")
                start += pos + len(r"\end{verbatim}")
            elif m[0] == begin_env:
                open_occ += 1           # another nested one
            else:           # end_env
                open_occ -= 1
                if open_occ == 0:
                    return start

    mangled_envs = ['align', 'align*',
                    'alignat', 'alignat*',
                    'eqnarray', 'eqnarray*'
                    'gather', 'gather*',
                    'multline', 'multline*',
                    ]
    mangled_envs = [re.escape(env) for env in mangled_envs]     # escapes '*'

    pos = 0
    while True:
        # Note: LyX puts `\begin` at the start of its line so we can use '^'.
        m = re.search(
            r'^\\begin{(%s)}|\\(ref|eqref){[^}]*}|\\begin{(verbatim)}'
            % "|".join(mangled_envs), latex[pos:], flags=re.MULTILINE)
        if m is None:
            break
        start = pos + m.start(0)
        end = pos + m.end(0)
        if m.lastindex == 3:        # verbatim
            pos = latex[end:].find(r"\end{verbatim}")
            if pos == -1:
                raise Exception("Can't find closing \end{verbatim}")
            end = end + pos     # we skip it
        elif m.lastindex == 2:      # (eq)ref
            yield start, end, 'inline'
        else:                       # math env
            end = find_end(m[1], start=end)
            yield start, end, 'block'
        pos = end


def protect_math_envs(latex):
    '''
    Protects latex math environments and \(eq)ref in the TeX file by wrapping
    them in '$$' and '$'. Otherwise, pandoc modifies them (e.g. align->aligned)
    and we lose equation numbering / labeling and referencing in MathJax.
    :param latex:   latex text
    :return: updated latex text
    '''
    output = []
    pos = 0
    for s, e, type in get_math_env_pos(latex):
        marker = '$$' if type == 'block' else '$'
        output.extend([latex[pos:s], marker, latex[s:e], marker])
        pos = e
    output.append(latex[pos:])

    return ''.join(output)


def add_mathjax_conf(html):
    conf = '''
        <script type="text/x-mathjax-config">
        MathJax.Hub.Config({
          TeX: { equationNumbers: { autoNumber: "AMS" } }
        });
        </script>
        '''
    pos = html.find('<head>')
    if pos == -1:
        raise Exception("Couldn't find <head> in html file!")
    pos += len('<head>')
    return html[:pos] + conf + html[pos:]


def main(script_path, argv):
    if len(argv) > 0 and argv[0] == '--update':
        update = True
        argv = argv[1:]
    else:
        update = False

    if len(argv) != 3:
        print_usage()
        sys.exit(2)
    lyx_path = argv[0]
    blog_dir = argv[1]
    assets_rel_dir = argv[2]

    filter_path = os.path.join(os.path.dirname(script_path), 'filter.py')

    # Change the working directory
    os.chdir(os.path.dirname(lyx_path))

    no_ext_path = os.path.splitext(lyx_path)[0]
    tex_path = no_ext_path + '.tex'
    md_path = no_ext_path + '.md'
    html_path = no_ext_path + '.html'

    # Preserve the extensions of image files (they're lost in the LyX -> TeX
    # conversion).
    name_to_ext = get_file_extensions(lyx_path)

    # LyX to TeX
    p = subprocess.run(['lyx', '--export', 'latex', lyx_path])
    if p.returncode != 0:
        raise Exception("Something's wrong with executing LyX!")

    # We get the front matter from the TeX file rather than directly from the
    # LyX file because this way we're independent of LyX's file format.
    front_matter = FrontMatter.from_file(tex_path)

    # Fix the TeX file to support labels and references through MathJax.
    with open(tex_path, 'r+', encoding='utf-8') as f:
        latex = f.read()
        f.seek(0)
        f.write(protect_math_envs(latex))

    # TeX to html
    p = subprocess.run(['pandoc', '-s', '--mathjax',
                        '--filter', filter_path,
                        '--filter', 'pandoc-citeproc',
                        '--metadata', 'link-citations=true',
                        '--metadata', 'reference-section-title=Bibliography',
                        '--number-sections',
                        tex_path, '-o', html_path])
    if p.returncode != 0:
        raise Exception("Something's wrong with executing pandoc!")

    # Transform the HTML file.
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Activates equation numbering support in MathJax.
    html = add_mathjax_conf(html)

    # Copy the images into the assets directory and fix their paths in the
    # HTML file
    html = handle_images(html, blog_dir, assets_rel_dir, front_matter,
                         name_to_ext, update)

    # Add the front matter to the HTML file.
    html = front_matter.front_matter + html

    # Write the html content into a properly named file in the correct subdir
    # in _posts.
    date_basename = get_date_basename(front_matter.html_file_name,
                                      front_matter.date)
    dest_html_path = os.path.join(blog_dir, '_posts', date_basename + '.html')
    if not update and os.path.exists(dest_html_path):
        raise Exception('Already exists: ' + dest_html_path)
    with open(dest_html_path, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == '__main__':
    # This is needed to hide other python installations.
    # LyX modifies PATH on-the-fly so this workaround is essential.
    os.environ['PATH'] = os.path.dirname(sys.executable) + ';' + \
                         os.environ['PATH']

    # argv1 = ["--update",
    #          r"D:\--- New Projects\mtomassoli.github.io\_lyx\distributional_rl"
    #             r"\distributional_rl.lyx",
    #          r"D:\--- New Projects\mtomassoli.github.io",
    #          "assets"
    # ]
    # main(sys.argv[0], argv1)
    main(sys.argv[0], sys.argv[1:])
