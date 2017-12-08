from pandocfilters import toJSONFilter, Header


# f = open('filter_num_log.txt', 'w', encoding='utf-8')

UID = 'guy76r856itybr6dv76e47igyuytb098hjkl'


def filter_main(key, value, format, meta):
    # f.write(repr(key) + '\n')
    # f.write(repr(value) + '\n')
    # f.write('------\n')
    if key == 'Header':
        # We use a unique id to identify the header in the html file more
        # safely.
        return Header(value[0], [UID, [], []], value[2])


if __name__ == "__main__":
    toJSONFilter(filter_main)
