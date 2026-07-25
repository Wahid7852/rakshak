# Provides RAKSHAK support for out.
import os

def write_dir_structure(startpath, output_file):
    """
    Writes the directory structure of a given path to a text file.

    Args:
        startpath (str): The starting directory path.
        output_file (str): The path to the output text file.
    """
    with open(output_file, 'w') as f:
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            f.write(f'{indent}{os.path.basename(root)}/\n')
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                f.write(f'{subindent}{file}\n')

# Example usage:
folder_to_list = "D:\\SHRI1\\cybersecurity challenge\\QUANTUM ML ARMY HACKATHON\\RAKSHAK Quantum ML Hunter"
output_text_file = 'directory_structure.txt'

write_dir_structure(folder_to_list, output_text_file)
print(f"Directory structure written to {output_text_file}")