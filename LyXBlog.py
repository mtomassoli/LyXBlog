import sys
import os
import shutil
import re
import subprocess
import datetime
import pickle
import ruamel_yaml as yaml


class FrontMatters:
    def __init__(self, our_fm, jekyll_fm):
        # Extracts html_file_name
        self.our_fm = our_fm
        self.jekyll_fm = jekyll_fm

        if 'html_file_name' not in our_fm:
            raise Exception('Front matter: the "html_file_name" attribute is '
                            'required!')

        # Extracts the date
        if ('date' not in jekyll_fm or
                type(jekyll_fm['date']) is not datetime.date):
            raise Exception('Missing or invalid "date" attribute in Jekyll\'s '
                            'front matter!')

    def dump_jekyll_fm(self):
        return ('---\n' +
                yaml.safe_dump(self.jekyll_fm, default_flow_style=False,
                               allow_unicode=True) +
                '---\n')

    def get_date_html_fname(self):
        return (self.jekyll_fm['date'].isoformat() + '-' +
                self.our_fm['html_file_name'])

    @staticmethod
    def _get_fm_limits(data):
        """
        Returns the `start` and `end` of the content, and `before` and `after`.
        """
        begin_str = r'\begin'
        begin_comment_str = r'\begin{comment}'
        end_comment_str = r'\end{comment}'
        begin_document_str = r'\begin{document}'

        pos = data.find(begin_document_str)
        if pos == -1:
            raise Exception('Malformed TeX file!')
        pos += len(begin_document_str)

        pos = data.find(begin_str, pos)
        if pos == -1:
            raise Exception('Malformed TeX file!')

        if not data[pos:].startswith(begin_comment_str):
            raise Exception("Can't find the Front Matter!")
        start = pos + len(begin_comment_str)

        end = data.find(end_comment_str, start)
        if end == -1:
            raise Exception("Can't find the closing \"\\end{comment}\" of "
                            "the Front Matter!")
        return (start, end, start - len(begin_comment_str),
                end + len(end_comment_str))

    @staticmethod
    def from_file(tex_path):
        with open(tex_path, 'r', encoding='utf-8') as f:
            data = f.read()
            start, end, _, _ = FrontMatters._get_fm_limits(data)

            try:
                # The last '---' produces a third empty "document".
                our_fm, jekyll_fm, _ = yaml.safe_load_all(data[start: end])
            except Exception:
                raise Exception("Something went wrong while parsing the "
                                "front matter!")

            return FrontMatters(our_fm, jekyll_fm)

    @staticmethod
    def remove_from_file(latex):
        # We assume the front matter is present and valid.
        _, _, before, after = FrontMatters._get_fm_limits(latex)
        return latex[:before] + latex[after:]


def handle_images(lyx_path, blog_dir, assets_rel_dir, front_matters,
                  update=True):
    """
    Copies the images into the assets directory and returns the correct path
    to use in the HTML file as image src.

    NOTE: when a LyX file is converted into a TeX file, the extensions of the
    image filenames are lost (e.g. picture.svg becomes picture).
    """

    our_fm = front_matters.our_fm

    assets_rel_dir = os.path.normpath(assets_rel_dir)

    # The images are created in a directory of the form
    #   blog_path/assets_rel_dir/date-html_fname
    # so that images of different articles are in separate directories.
    date_html_fname = front_matters.get_date_html_fname()
    rel_dest_dir = os.path.join(assets_rel_dir, date_html_fname)
    dest_dir = os.path.join(blog_dir, rel_dest_dir)

    image_info = []
    name_to_num = {}

    image_num = 1
    image_http_path = None
    image_label = None

    # NOTE:
    #   - In LyX files, '\' can only appear in commands, so searching for, say,
    #     '\begin_inset' is safe.
    with open(lyx_path, encoding='utf-8') as f:
        # in_* remember the nesting level; -1 = not inside
        in_graphics = -1
        in_float_figure = -1
        in_label = -1

        nesting = 0

        for line in f:
            if line.startswith(r'\begin_inset Float figure'):
                in_float_figure = nesting       # we're in
            if line.startswith(r'\begin_inset Graphics'):
                in_graphics = nesting           # we're in
            if (line.startswith(r'\begin_inset CommandInset label') and
                    in_float_figure != -1):         # only if in float figure
                in_label = nesting              # we're in

            we_were_in = (in_graphics != -1 or
                          in_float_figure != -1 or
                          in_label != -1)

            # We handle the nesting of begin_ and end_inset.
            if line.startswith(r'\begin_inset'):
                nesting += 1
            elif line.startswith(r'\end_inset'):
                nesting -= 1
                if in_graphics == nesting:
                    in_graphics = -1            # we're out
                if in_float_figure == nesting:
                    in_float_figure = -1        # we're out
                if in_label == nesting:
                    in_label = -1               # we're out

            we_are_in = (in_graphics != -1 or
                         in_float_figure != -1 or
                         in_label != -1)

            if we_were_in and not we_are_in:        # we exited
                # We write the data collected so far.
                if image_http_path is None:
                    raise Exception("LyX file: couldn't get image http path!")
                image_info.append(image_http_path)
                if image_label:
                    name_to_num[image_label] = str(image_num)
                image_num += 1

                # reset
                image_http_path = None
                image_label = None

            if in_graphics != -1:
                # format:
                #    filename discrete fgfg.svg
                m = re.match(r'\s*filename\s+(.+)$', line)
                if m:
                    src_path = m[1]
                    base_name = os.path.basename(src_path)
                    dest_path = os.path.join(dest_dir, base_name)
                    if not update and os.path.exists(dest_path):
                        raise Exception('Already exists: ' + dest_path)

                    # Create the directory and copy the file
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy(src_path, dest_path)

                    # Return the blog-relative path of the copied image
                    image_http_path = ('/' + assets_rel_dir + '/' +
                                       date_html_fname + '/' + base_name)

            if in_float_figure != -1 and in_label != -1:
                # format:
                #    name "fig:label_per_figure"
                m = re.match(r'\s*name\s+"([^"]+)"$', line)
                if m:
                    image_label = m[1]

    return image_info, name_to_num


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
                pos = latex.find(r"\end{verbatim}", start)
                if pos == -1:
                    raise Exception("Can't find closing \end{verbatim}")
                start = pos + len(r"\end{verbatim}")
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
            pos = latex.find(r"\end{verbatim}", end)
            if pos == -1:
                raise Exception("Can't find closing \end{verbatim}")
            end = pos           # we skip it
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
        <script type="text/javascript" 
            src="//cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.2/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
        </script>
        <script type="text/x-mathjax-config">
        MathJax.Hub.Config({
          TeX: { equationNumbers: { autoNumber: "AMS" } }
        });
        </script>
        '''
    return conf + html


def get_section_label_info(html_path):
    UID = 'guy76r856itybr6dv76e47igyuytb098hjkl'    # see filter_num.py
    re_str = (r'^<h. id="' + UID +
              r'"><span class="header-section-number">([^<]+)' +
              r'</span>(.*)</h.>$')

    section_info = []
    name_to_num = {}
    with open(html_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = re.match(re_str, line, flags=re.I)
            if m:
                num = m[1]
                name = m[2]
                m2 = re.match(r'.*\[([^]]+)\]', name)
                label_name = m2[1] if m2 else None
                section_info.append((m[0], num, name, label_name))
                if label_name:
                    name_to_num[label_name] = num
    return section_info, name_to_num


def fix_figure_tag(html):
    UID2 = '86345huihsdfguhsjlkertvxgkh3498asdg'
    new_html = []
    start = 0
    while True:
        m = re.search(r'<figure()>\n<img src=.*?({}:([^"]+))'.format(UID2),
                      html[start:])
        if m is None:
            break

        pos1 = start + m.start(1)
        new_html.append(html[start: pos1])

        new_html.append(' style="margin-left: {}; margin-right: {};"'
                        .format(m[3], m[3]))

        # Remove the fake class from image
        pos2 = start + m.start(2)       # right before fake class
        pos3 = start + m.end(2)         # right after fake class
        pos4 = start + m.end(0)
        new_html.append(html[pos1: pos2])
        new_html.append(html[pos3: pos4])

        start = pos4

    new_html.append(html[start:])

    return ''.join(new_html)


def add_style_text(html, style_text):
    return '<style>' + style_text + '</style>' + html


def print_usage():
    print('LyXBlog [--update] [--args_from_file] <input file> <blog base dir> '
          '<assets relative dir>')


def main(script_path, argv):
    update = False
    args_from_file = False
    if '--update' in argv:
        update = True
        argv.remove('--update')
    if '--args_from_file' in argv:
        args_from_file = True
        argv.remove('--args_from_file')

    if args_from_file:
        if len(argv) != 1:
            print_usage()
            sys.exit(2)
        lyx_path = argv[0]
    else:
        if len(argv) != 3:
            print_usage()
            sys.exit(2)
        lyx_path, blog_dir, assets_rel_dir = argv

    filter_num_path = os.path.join(os.path.dirname(script_path),
                                   'filter_num.py')
    filter_path = os.path.join(os.path.dirname(script_path), 'filter.py')

    # Change the working directory
    os.chdir(os.path.dirname(lyx_path))

    no_ext_path = os.path.splitext(lyx_path)[0]
    tex_path = no_ext_path + '.tex'
    html_path = no_ext_path + '.html'

    # LyX to TeX
    p = subprocess.run(['lyx', '--export', 'latex', lyx_path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise Exception("Something's wrong with executing LyX:\n" +
                        str(p.stdout, 'utf-8') + "\n")

    # We get the front matter from the TeX file rather than directly from the
    # LyX file because it's simpler.
    front_matters = FrontMatters.from_file(tex_path)

    if args_from_file:
        args = front_matters.our_fm.get('args', None)
        if args is None:
            raise Exception("Can't find 'args' in front matter!")
        try:
            blog_dir = args['blog_base_dir']
            assets_rel_dir = args['assets_rel_dir']
        except KeyError as e:
            raise Exception("Can't find {} in 'args' in front matter!"
                            .format(e))

    # Copies the images into the assets directory and returns the correct path
    # to use in the HTML file as image src.
    image_info_and_map = handle_images(lyx_path, blog_dir, assets_rel_dir,
                                       front_matters, update)
    pickle.dump(image_info_and_map, open('lyxblog_image_info.p', 'wb'))

    with open(tex_path, 'r+', encoding='utf-8') as f:
        latex = f.read()

        # Fix the TeX file to support labels and references through MathJax.
        latex = protect_math_envs(latex)

        # Remove the front matter.
        latex = FrontMatters.remove_from_file(latex)

        f.seek(0)
        f.write(latex)
        f.truncate()

    # TeX to html
    p = subprocess.run(['pandoc', '--mathjax',
                        '--filter', filter_num_path,
                        '--number-sections',
                        tex_path, '-o', html_path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise Exception("Something's wrong with executing pandoc:\n" +
                        str(p.stdout, 'utf-8') + "\n")

    section_info_and_map = get_section_label_info(html_path)
    pickle.dump(section_info_and_map, open('lyxblog_label_info.p', 'wb'))

    # TeX to html
    p = subprocess.run(['pandoc', '--mathjax',
                        '--filter', filter_path,
                        '--filter', 'pandoc-citeproc',
                        '--metadata', 'link-citations=true',
                        '--metadata', 'reference-section-title=Bibliography',
                        '--number-sections',
                        tex_path, '-o', html_path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise Exception("Something's wrong with executing pandoc:\n" +
                        str(p.stdout, 'utf-8') + "\n")

    # Transform the HTML file.
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    if 'style' in front_matters.our_fm:
        html = add_style_text(html, front_matters.our_fm['style'])

    html = fix_figure_tag(html)

    # Activates equation numbering support in MathJax.
    html = add_mathjax_conf(html)

    # Prepend Jekyll's front matter to the HTML file.
    html = front_matters.dump_jekyll_fm() + html

    # Write the html content into a properly named file in the correct subdir
    # in _posts.
    date_basename = front_matters.get_date_html_fname()
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
    #          "--args_from_file",
    #          r"D:\--- New Projects\MLBlogSource\distributional_rl"
    #          r"\distributional_rl.lyx",
    #          ]
    # main(sys.argv[0], argv1)

    main(sys.argv[0], sys.argv[1:])
