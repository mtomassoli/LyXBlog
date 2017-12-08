# AST defs: search for "Text-Pandoc-Definition.html"

from pandocfilters import toJSONFilter, RawBlock, Math, RawInline, Para,\
    Image, Emph, Str, Space, Span, Header
import re
import pickle

# f = open('filter_log.txt', 'w', encoding='utf-8')

UID = 'guy76r856itybr6dv76e47igyuytb098hjkl'
header_idx = 0
image_idx = 0

UID2 = '86345huihsdfguhsjlkertvxgkh3498asdg'

section_info, sec_name_to_num = pickle.load(open('lyxblog_label_info.p', 'rb'))
image_info, img_name_to_num = pickle.load(open('lyxblog_image_info.p', 'rb'))


def make_attrs(id, classes, style_dict):
    return id, classes, list(style_dict.items())


def filter_main(key, value, format, meta):
    # f.write(repr(key) + '\n')
    # f.write(repr(value) + '\n')
    # f.write('------\n')
    if key == 'CodeBlock':
        text = value[1]
        m = re.match(r'%%%%lyxblog-raw\n(.*)', text, flags=re.DOTALL | re.I)
        if m:
            return RawBlock('html', m[1])
    elif key == 'Math' and value[0]['t'] == 'DisplayMath':  # i.e. not inline
        # MathJax supports labels and eq. numbering only for AMS envs, so we
        # convert non-AMS envs into AMS envs.
        latex = value[1]
        if not latex.startswith(r'\begin{'):        # not AMS env
            # We assume there are no comments inside math blocks (if the file
            # is produced by LyX, there shouldn't be any).
            pos = latex.find(r'\label{')
            if pos == -1:           # no labels => no numbering
                fixed = r'\begin{align*}' + value[1] + r'\end{align*}'
            else:
                fixed = r'\begin{align}' + value[1] + r'\end{align}'
            return Math(value[0], fixed)
    elif key == 'Span':
        # This supports general labels (i.e. labels not in equations, captions
        # or section headers).
        id, classes, key_values = value[0]
        if len(key_values) == 1 and key_values[0][0] == 'label':
            # we remove the text from the label.
            return Span(value[0], [])
    elif key == 'Header':
        content = value[2]
        if content[-1]['t'] == 'Span':
            [id, classes, key_values], text = content[-1]['c']
            if len(key_values) == 1 and key_values[0][0] == 'label':
                # we label the header itself (id) and delete the label-span
                label_name = key_values[0][1]
                value[1][0] = label_name
                return Header(value[0], value[1], content[:-1])
    elif key == 'Math' and value[0]['t'] == 'InlineMath':
        if value[1].startswith('\\ref{') and value[1][-1] == '}':
            name = value[1][len('\\ref{'): -1]

            # We try to extract the text from the label itself.
            # (=00007B and =00007D represent '{' and '}' and are in the TeX
            # file produced by LyX.)
            m = re.match(r'.*=00007B([^}]+)=00007D$', name)
            if m:
                return RawInline(
                    'html', '<a href="#{}">{}</a>'.format(name, m[1]))

            # We only handle references to sections and images here.
            # (Mathjax already handles the equations.)
            num = sec_name_to_num.get(name,
                                      img_name_to_num.get(name, None))
            if num:
                return RawInline(
                    'html', '<a href="#{}">{}</a>'.format(name, num))

    elif key == 'Para' and value[0]['t'] == 'Image':
        # NOTE:
        #   In pandoc 2, a Para[Image] where Image.title is 'fig:' becomes
        #   a <figure> with a <figcaption>.

        [id, classes, style], alt, [src, title] = value[0]['c']
        style = {k: v for k, v in style}
        width = float(style.get('width', '100.0%')[:-1])
        margin = (100 - width) / 2

        global image_idx
        src = image_info[image_idx]
        image_idx += 1

        label = ''
        if alt[-1]['t'] == 'Span':
            id, classes, key_values = alt[-1]['c'][0]       # attr
            key_values = dict(key_values)
            if 'label' in key_values:
                # remove the label from the caption (it'll be put right before
                # the image).
                alt = alt[:-1]      # remove the label from the caption
                label = key_values['label']

        fake_class = '{}:{:.5}%'.format(UID2, margin)
        img_attrs = make_attrs(label, [fake_class], {'width': '100%'})
        caption = [Emph([Str('Figure {}.'.format(image_idx))])]
        if title == 'fig:':
            caption += [Space()] + alt

        para_content = [Image(img_attrs, caption, (src, 'fig:'))]

        return Para(para_content)


if __name__ == "__main__":
    toJSONFilter(filter_main)
