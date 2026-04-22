content = open('.github/workflows/release.yml', encoding='utf-8').read()

# Find and replace the body section
lines = content.split('\n')
new_lines = []
skip = False
for i, line in enumerate(lines):
    if '          body: |' in line:
        skip = True
        new_lines.append('          body_path: docs/RELEASE_NOTES.md')
        continue
    if skip and '          draft: false' in line:
        skip = False
    if not skip:
        new_lines.append(line)

open('.github/workflows/release.yml', 'w', encoding='utf-8').write('\n'.join(new_lines))
print('Done')
print('Lines around fix:')
result = '\n'.join(new_lines)
idx = result.find('body_path')
print(result[max(0,idx-100):idx+100])