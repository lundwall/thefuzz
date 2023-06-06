#! /bin/sh



# sed -n '/- name: Create a file without a path/{p; :a; N; /      - create_no_path_file.stat.exists/!ba; s/.*\n//}; p' /mnt/test/tasks/main.yml

# sed '/- name: Create a file without a path/,/- create_no_path_file.stat.exists/{//!d;}' /mnt/test/tasks/main.yml

# sed -i 's/(- name: Create a file without a path).*(- create_no_path_file.stat.exists)/\1 foo \2/g' /mnt/test/tasks/main.yml


## First remove the line that fixes the python code
sed -i '/if b_destpath and not os.path.exists(b_destpath) and not module.check_mode:/c\        if not os.path.exists(b_destpath) and not module.check_mode:' /usr/local/lib/python3.10/site-packages/ansible/modules/lineinfile.py

## Then remove the testcases that were found after discovering the bug
python -c "
print('Removing New test cases that were added afrer bug')
flag = 1
newlines = []
count = 0
with open('/mnt/test/tasks/main.yml') as infile:
  linelist = infile.readlines()
  for line in linelist:
    if '- name: Create a file without a path' in line:
      flag = 0
    if flag:
      newlines.append(line)
    else:
      count += 1
    if '- create_no_path_file.stat.exists' in line:
      flag = 1
with open('/mnt/test/tasks/main.yml', 'w') as infile:
  infile.writelines(newlines)
print(f'{count} lines removed')

"