import openai
import base64
import os
import io
from PIL import Image
from abc import ABCMeta, abstractmethod


def create_vision_chat_completion(base64_image, prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except:
        return None


def image_to_base64(path):
    try:
        _, suffix = os.path.splitext(path)
        if suffix not in {'.jpg', '.jpeg', '.png', '.webp'}:
            img = Image.open(path)
            img_png = img.convert('RGB')
            img_png.tobytes()
            byte_buffer = io.BytesIO()
            img_png.save(byte_buffer, 'PNG')
            encoded_string = base64.b64encode(byte_buffer.getvalue()).decode('utf-8')
        else:
            with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    except:
        return None


def inquire_image(workdir, path, prompt):
    image_base64 = image_to_base64(f'{workdir}/{path}')
    hypertext_to_display = None
    if image_base64 is None:
        return "Error: Image transform error", None
    else:
        response = create_vision_chat_completion(image_base64, prompt)
        if response is None:
            return "Model response error", None
        else:
            return response, hypertext_to_display


class Tool(metaclass=ABCMeta):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def support(self):
        pass

    @abstractmethod
    def get_tool_data(self):
        pass


class ImageInquireTool(Tool):
    def support(self):
        return self.config['model']['GPT-4V']['available']

    def get_tool_data(self):
        return {
            "tool_name": "inquire_image",
            "tool": inquire_image,
            "system_prompt": "If needed, utilize the 'inquire_image' tool to query an AI model regarding the content "
                             "of images uploaded by users. Avoid phrases like\"based on the analysis\"; "
                             "instead, respond as if you viewed the image by yourself.",
            "tool_description": {
                "name": "inquire_image",
                "description": "This function enables you to inquire with an AI model about the contents of an image "
                               "and receive the model's response.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path of the image"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "The question you want to pose to the AI model about the image"
                        }
                    },
                    "required": ["path", "prompt"]
                }
            }
        }


def get_available_tools(config):
    tools = [ImageInquireTool]

    available_tools = []
    for tool in tools:
        tool_instance = tool(config)
        if tool_instance.support():
            available_tools.append(tool_instance.get_tool_data())
    return available_tools
