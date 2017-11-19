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
        self.html_file_name = m.group(1)

        # Extracts the date
        m = re.search(r'^date:\s*(.+)\s*$', self.front_matter, flags=re.M)
        self.date = m.group(1)
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
                        fname = m.group(1)
                        path_ext = os.path.splitext(fname)
                        name_to_ext[path_ext[0]] = path_ext[1][1:]
                        found = False
            elif line.startswith(r'\begin_inset Graphics'):
                found = True
    return name_to_ext


def get_date_basename(path, date):
    return date + '-' + os.path.basename(path)


def handle_images(html_path, blog_path, assets_rel_dir, front_matter,
                  name_to_ext, update=True):
    """
    Copy the images into the assets directory and fix their path in the HTML
    file.
    """
    assets_rel_dir = os.path.normpath(assets_rel_dir)

    with open(html_path, encoding='utf-8') as f:
        data = f.read()

    # The images are created in a directory of the form
    #   blog_path/assets_rel_dir/date-html_fname
    # so that images of different articles are in separate directories.
    date_html_fname = get_date_basename(front_matter.html_file_name,
                                        front_matter.date)
    rel_dest_dir = os.path.join(assets_rel_dir, date_html_fname)
    dest_dir = os.path.join(blog_path, rel_dest_dir)

    def replace_group(match, group, new_text):
        start = match.start(group) - match.start(0)
        end = match.end(group) - match.start(0)
        return match[0][:start] + new_text + match[0][end:]

    def fix(match):
        full_path = match.group(1)
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
            return replace_group(match, 1, path)
        return full_path            # no fixing

    data = re.sub(r'<img src="([^"]*)"', fix, data)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(data)


def main(argv):
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
    assets_dir = os.path.join(blog_dir, assets_rel_dir)

    # Change the working directory
    os.chdir(os.path.dirname(lyx_path))

    no_ext_path = os.path.splitext(lyx_path)[0]
    base_name = os.path.basename(no_ext_path)
    tex_path = no_ext_path + '.tex'
    html_path = no_ext_path + '.html'

    # Preserve the extensions of image files (they're lost in the LyX -> TeX
    # conversion).
    name_to_ext = get_file_extensions(lyx_path)

    # LyX to TeX
    p = subprocess.run(['lyx', '--export', 'latex', lyx_path])
    if p.returncode != 0:
        raise Exception("Something's wrong with executing LyX!")

    # TeX to HTML
    p = subprocess.run(['pandoc', '-s', '--mathjax', tex_path, '-o',
                        html_path])
    if p.returncode != 0:
        raise Exception("Something's wrong with executing pandoc!")

    # We get the front matter from the TeX file rather than directly from the
    # LyX file because this way we're independent from LyX's file format.
    front_matter = FrontMatter.from_file(tex_path)

    # Copy the images into the assets directory and fix their paths in the
    # HTML file
    handle_images(html_path, blog_dir, assets_rel_dir, front_matter, name_to_ext,
                  update)

    # Add the front matter to the HTML file and copy it into the correct
    # subdir in _posts.
    with open(html_path, encoding='utf-8') as f:
        data = f.read()
    date_basename = get_date_basename(front_matter.html_file_name, front_matter.date)
    dest_html_path = os.path.join(blog_dir, '_posts', date_basename + '.html')
    if not update and os.path.exists(dest_html_path):
        raise Exception('Already exists: ' + dest_html_path)
    with open(dest_html_path, 'w', encoding='utf-8') as f:
        f.write(front_matter.front_matter)
        f.write(data)


if __name__ == '__main__':
    # argv = ['--update',
    #         r'C:\Users\Kiuhnm\Documents\RL_notes.lyx',
    #         r'D:\--- New Projects\mtomassoli.github.io',
    #         'assets']
    # main(argv)
    main(sys.argv[1:])
