import nbformat
from nbformat import v4 as nbf
import ansi2html
import sys
import os
import json

# Get UNIQUE notebook path with argv and cwd


# Global variable for code cells
notebbok_cells = []

def ansi_to_html(ansi_text):
    converter = ansi2html.Ansi2HTMLConverter()
    html_text = converter.convert(ansi_text)
    return html_text

def serialize_conv_into_notebook():

    nb = nbf.new_notebook()
    try:
        for cell in notebbok_cells:
            if cell['type'] == 'code':
                code_cell = nbf.new_code_cell(source=cell['code'])
                for output in cell['outputs']:
                    if output['type'] == 'stdout':
                        html_content = ansi_to_html(output['content'])
                        code_cell['outputs'].append(nbf.new_output(output_type='display_data', data={'text/html': html_content}))
                    elif output['type'] == 'error':
                        # Convert ANSI to HTML and add as display_data instead of traceback
                        html_content = ansi_to_html(output['content'])
                        nbf_error_output = nbf.new_output(
                            output_type='error',
                            ename='Error',
                            evalue='Error message',
                            traceback=[output['content']]
                        )
                        code_cell['outputs'].append(nbf_error_output)
                    elif 'image' in output['type']:
                        code_cell['outputs'].append(nbf.new_output(output_type='display_data', data={output['type']: output['content']}))
                nb['cells'].append(code_cell)
            
            if cell['type'] == 'markdown':
                markdown_cell = nbf.new_markdown_cell(cell['markdown'])
                nb['cells'].append(markdown_cell)
    except Exception as e:
        print(f"Caught error during conv serialization: '{e}'")

    # Save the notebook
    with open('output_notebook.ipynb', 'w') as f:
        nbformat.write(nb, f)