import argparse
import json
import tempfile
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import fitz  # PyMuPDF
import requests
from autogen import AssistantAgent, ConversableAgent, UserProxyAgent
from autogen.agentchat.contrib.capabilities import transform_messages
from autogen.agentchat.contrib.capabilities.text_compressors import LLMLingua
from autogen.agentchat.contrib.capabilities.transforms import TextMessageCompressor


def load_config():
    with open("config.json", "r") as file:
        return json.load(file)


def configure_llm(tmp):
    return {
        "config_list": [tmp],
        "cache_seed": None,  # Turns off caching, useful for testing different models
    }


def download_pdf(url):
    response = requests.get(url)
    response.raise_for_status()  # Ensure the download was successful
    return response.content


def extract_text_from_pdf(pdf_content):
    text = ""
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(temp_dir + "temp.pdf", "wb") as f:
            f.write(pdf_content)

        with fitz.open(temp_dir + "temp.pdf") as doc:
            for page in doc:
                text += page.get_text()

    return text


def create_agents(llm_config, system_message):
    researcher = ConversableAgent(
        "assistant",
        llm_config=llm_config,
        max_consecutive_auto_reply=1,
        system_message=system_message,
        human_input_mode="NEVER",
    )

    user_proxy = UserProxyAgent(
        "user_proxy",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
        max_consecutive_auto_reply=1,
        code_execution_config={
            "last_n_messages": 1,
            "work_dir": "tmp",
            "use_docker": False,
        },
    )

    context_handling = transform_messages.TransformMessages(
        transforms=[TextMessageCompressor()]
    )
    context_handling.add_to_agent(researcher)

    return researcher, user_proxy


def main(paper_url):
    tmp = load_config()
    llm_config = configure_llm(tmp)
    pdf_content = download_pdf(paper_url)
    pdf_text = extract_text_from_pdf(pdf_content)
    researcher, user_proxy = create_agents(
        llm_config,
        """
        You are a world class researcher and please explain the topic, methods and results from the text.
        """,
    )
    message = (
        "What kind of research does this paper conduct? Please explain the main topic and methods."
        + pdf_text
    )
    result = user_proxy.initiate_chat(
        recipient=researcher, clear_history=True, message=message, silent=True
    )
    print(result.chat_history[1]["content"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize a research paper.")
    parser.add_argument(
        "-p",
        "--paper_url",
        type=str,
        default="https://arxiv.org/pdf/2405.08979",
        help="URL to the PDF to summarize.",
    )
    args = parser.parse_args()
    main(args.paper_url)
