import io, sys
name = sys.argv[1]
raw = open(name, 'r', encoding='utf-8', errors='replace').read()
fixed = raw.replace('\\n', '\n').replace('\\t', '\t')
out = name.replace('.txt', '_lines.txt')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(fixed)
print('%s lines=%d' % (out, fixed.count('\n')))
