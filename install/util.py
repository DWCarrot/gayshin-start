
from io import TextIOWrapper


def template(ifile: TextIOWrapper, ofile: TextIOWrapper, **kwargs) -> None:
    """
    Replace the template variables in the input file and write the result to the output file.
    """
    for line in ifile:
        new_line = None
        last = 0
        i = line.find('%', last)
        while i > 0:
            j = line.find('%', i + 1)
            if j <= i:
                raise ValueError('Invalid template variable: empty')
            key = line[i+1:j]
            value = kwargs.get(key)
            if value is None:
                raise ValueError('Invalid template variable: {}'.format(key))
            if new_line is None:
                new_line = line[last:i]
            else:
                new_line += line[last:i]
            new_line += value
            last = j + 1
            i = line.find('%', last)
        if new_line is not None:
            new_line += line[last:]
            line = new_line
        ofile.write(line)



if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: {} <input> <output> [key=value ...]'.format(sys.argv[0]), file=sys.stderr)
        sys.exit(1)
    ifile_name = sys.argv[1]
    ofile_name = sys.argv[2]
    variables = dict(arg.split('=') for arg in sys.argv[3:])
    print('variables:', variables)
    with open(ifile_name, 'r') as ifile:
        with open(ofile_name, 'w') as ofile:
            template(ifile, ofile, **variables)