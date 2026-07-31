import os
os.environ['HF_EBNDPOINT']='https://hf-mirror.com'
os.environ['HF_HOME']='./data'
from transformers import AutoTokenizer, AutoModel

tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-large-zh-v1.5")
model = AutoModel.from_pretrained("BAAI/bge-large-zh-v1.5", device_map="auto")