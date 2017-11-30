from pandocfilters import toJSONFilter, RawBlock, Math, CodeBlock
import re

# f = open('filter_log.txt', 'w')

def filter_main(key, value, format, meta):
    # f.write(repr(key) + '\n')
    # f.write(repr(value) + '\n')
    # f.write('------\n')
    if key == 'CodeBlock':
        text = value[1]
        m = re.match(r'%%%%lyxblog-raw\n(.*)', text, flags=re.DOTALL | re.I)
        if m:
            return RawBlock(format, m[1])
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


if __name__ == "__main__":
    toJSONFilter(filter_main)
