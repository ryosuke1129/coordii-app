from openai import OpenAI
import base64

client = OpenAI()

prompt = """Generate a photorealistic fashion image of the person shown in the first image, wearing the clothing items shown in the subsequent images."""

def encode_image(file_path):
    with open(file_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")
    return base64_image

file_id1 = encode_image("/Users/rk-mac/Downloads/IMG_0515.jpg")
file_id2 = encode_image("/Users/rk-mac/Downloads/IMG_0455.jpg")
file_id3 = encode_image("/Users/rk-mac/Downloads/IMG_0463.jpg")
file_id4 = encode_image("/Users/rk-mac/Downloads/IMG_0467.jpg")
file_id5 = encode_image("/Users/rk-mac/Downloads/IMG_0468.jpg")

response = client.responses.create(
    model="gpt-5-mini",
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{file_id1}"
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{file_id2}"
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{file_id3}"
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{file_id4}"
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{file_id5}"
                },
            ],
        }
    ],
    tools=[{"type": "image_generation"}],
)

image_generation_calls = [
    output
    for output in response.output
    if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
    image_base64 = image_data[0]
    with open("/Users/rk-mac/Downloads/gift.png", "wb") as f:
        f.write(base64.b64decode(image_base64))
else:
    print(response.output.content)