"""
Gradio frontend for Agentic RAG.

Provides a chat interface with document upload, easily replaceable with Streamlit.
All backend communication uses async HTTP for non-blocking UI.
"""

import asyncio
from pathlib import Path

import gradio as gr
import httpx
from dotenv import load_dotenv
from loguru import logger

from rag.config import Config, load_config

# Load environment variables from .env file
env_path = Path(__file__).parents[3] / ".env"
load_dotenv(dotenv_path=env_path)


class RAGChatInterface:
    """
    Gradio chat interface for RAG system.

    This class is designed with UI-backend separation in mind:
    - All backend calls use HTTP API (not direct imports)
    - Easy to swap Gradio for Streamlit or other UI frameworks
    - Async HTTP client for non-blocking requests

    Why async HTTP for the frontend:
    1. Document uploads can take 5-15 seconds (I/O-bound)
    2. Query responses can take 5-30+ seconds (LLM generation)
    3. Async prevents UI freezing during backend operations
    4. Users can interact with UI while requests are processing

    Attributes:
        config: Frontend configuration.
        api_base_url: Base URL for backend API.
        client: Async HTTP client for API calls.
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize the chat interface.

        Args:
            config: Application configuration.
        """
        self.config = config
        
        # Use environment variables for Docker deployment, fallback to config
        import os
        backend_host = os.getenv("BACKEND_HOST", config.api.host)
        backend_port = os.getenv("BACKEND_PORT", str(config.api.port))
        
        self.api_base_url = f"http://{backend_host}:{backend_port}"
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for long LLM calls

        logger.info(f"Initialized RAG chat interface: {self.api_base_url}")

    async def upload_file(self, file) -> str:
        """
        Upload a file to the backend.

        This is async because:
        1. File upload involves network I/O (can be several MB)
        2. Backend processing takes 5-15 seconds
        3. UI should remain responsive during upload

        Args:
            file: Uploaded file object from Gradio.

        Returns:
            Status message with warnings if in fallback mode.
        """
        if file is None:
            return "Please select a file to upload."

        try:
            # Handle both file objects and string paths
            if isinstance(file, str):
                file_path = file
                file_name = file_path.split("/")[-1]
                logger.info(f"Uploading file from path: {file_path}")
            else:
                file_path = file.name
                file_name = file.name
                logger.info(f"Uploading file object: {file_name}")

            with open(file_path, "rb") as f:
                files = {"file": (file_name, f)}
                response = await self.client.post(
                    f"{self.api_base_url}/upload",
                    files=files,
                )

            if response.status_code == 200:
                result = response.json()
                message = (
                    f"✅ Successfully uploaded {file_name}!\n\n"
                    f"📄 Documents: {result['num_documents']}\n"
                    f"📝 Chunks: {result['num_chunks']}\n"
                    f"🆔 IDs: {len(result['document_ids'])} chunks added"
                )

                # Add warnings if present (fallback mode)
                if result.get("warnings"):
                    message += "\n\n" + "─" * 50 + "\n"
                    for warning in result["warnings"]:
                        message += f"\n{warning}"
                    message += "\n" + "─" * 50

                logger.info(f"Upload successful: {file_name}")
                return message
            else:
                error_msg = f"❌ Upload failed: {response.text}"
                logger.error(error_msg)
                return error_msg

        except Exception as e:
            import traceback

            error_msg = f"❌ Error uploading file: {str(e)}"
            full_traceback = traceback.format_exc()
            logger.error(f"{error_msg}\n\nFull traceback:\n{full_traceback}")
            return f"{error_msg}\n\n```\n{full_traceback}\n```"

    async def query_rag(self, message: str, history: list[dict[str, str]]) -> str:
        """
        Query the RAG system.

        This is async because:
        1. Query processing involves LLM generation (5-30+ seconds)
        2. Network I/O for API call
        3. UI must remain responsive during generation

        Args:
            message: User message.
            history: Chat history.

        Returns:
            RAG response with warnings if in fallback mode.
        """
        if not message:
            return "Please enter a question."

        try:
            logger.info(f"Querying RAG: {message[:100]}...")

            response = await self.client.post(
                f"{self.api_base_url}/query",
                json={"query": message, "top_k": 5},
            )

            if response.status_code == 200:
                result = response.json()
                answer = result["answer"]

                # Add warnings if present (fallback mode)
                if result.get("warnings"):
                    answer = "─" * 50 + "\n"
                    for warning in result["warnings"]:
                        answer += f"{warning}\n"
                    answer += "─" * 50 + "\n\n" + result["answer"]

                # Add sources if available
                if result.get("sources"):
                    answer += "\n\n📚 **Sources:**\n"
                    for i, source in enumerate(result["sources"], 1):
                        metadata = source["metadata"]
                        source_info = metadata.get("source", "Unknown")
                        answer += f"\n{i}. {source_info}"

                logger.info("Query successful")
                return answer
            else:
                error_msg = f"❌ Query failed: {response.text}"
                logger.error(error_msg)
                return error_msg

        except Exception as e:
            import traceback

            error_msg = f"❌ Error querying RAG: {str(e)}"
            full_traceback = traceback.format_exc()
            logger.error(f"{error_msg}\n\nFull traceback:\n{full_traceback}")
            return f"{error_msg}\n\n```\n{full_traceback}\n```"

    def create_interface(self) -> gr.Blocks:
        """
        Create the Gradio interface.

        Uses modern Gradio features:
        - Blocks for custom layout
        - ChatInterface-style interaction
        - File upload with multimodal support
        - Streaming responses
        - Like/dislike feedback

        Returns:
            Gradio Blocks interface.
        """
        custom_css = """
        .gradio-container {
            font-family: 'Inter', sans-serif;
        }
        """

        with gr.Blocks(
            title=self.config.frontend.title,
            theme=gr.themes.Soft(primary_hue="blue"),
            css=custom_css,
            fill_height=True,
        ) as interface:
            # Title and description
            gr.Markdown(
                f"""
                <h1 style='text-align: center;'>🤖 {self.config.frontend.title}</h1>
                <h3 style='text-align: center;'>{self.config.frontend.description}</h3>
                """
            )
            
            # Main chat area
            chatbot = gr.Chatbot(
                type="messages",
                label="💬 Chat",
                height=650,
                placeholder="""

    
    ═══════════════════════════════════════════════
    
    Step 1:  Click the attachment button below
    
    Step 2:  Upload your document
    
    Step 3:  Ask questions about the content
    
    Step 4:  Get AI-powered answers with sources!
    
    ═══════════════════════════════════════════════
    

""",
                show_copy_button=False,
                show_share_button=False,
                elem_id="chatbot",
            )

            chat_input = gr.MultimodalTextbox(
                interactive=True,
                file_count="multiple",
                placeholder="Enter message or upload file...",
                show_label=False,
                stop_btn=True,
                autofocus=True,
                sources=["upload"],
            )

            gr.Examples(
                examples=[
                    "What is this document about?",
                    "Summarize the main points",
                    "List key findings",
                ],
                inputs=chat_input,
            )

            # Settings and information section below chat (collapsible)
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Accordion("⚙️ Settings", open=False):
                        gr.Markdown(
                            """
                            Adjust these settings to customize your RAG experience.
                            Changes apply to the next query.
                            """
                        )
                        _top_k = gr.Slider(  # noqa: F841
                            minimum=1,
                            maximum=10,
                            value=5,
                            step=1,
                            label="Retrieved Documents",
                            info="Number of context chunks to retrieve",
                        )

                with gr.Column(scale=1):
                    with gr.Accordion("ℹ️ Information", open=False):
                        gr.Markdown(
                            f"""
                            **System Configuration:**
                            
                            - **Max file size:** {self.config.app.max_upload_size_mb}MB
                            - **Supported formats:** PDF, DOCX, TXT, Images
                            - **LLM Provider:** {self.config.llm.provider}
                            - **Embeddings:** {self.config.embeddings.provider}
                            
                            *To change these settings, modify the `config.yaml` file and restart the application.*
                            """
                        )

                with gr.Column(scale=1):
                    with gr.Accordion("💡 Tips & Help", open=False):
                        gr.Markdown(
                            """
                            **Quick Tips:**
                            
                            - 📎 Upload files directly using the attachment button in the chat input
                            - 🛑 Use the stop button to interrupt long responses
                            - 🗑️ Clear chat history using the clear button in the chatbot header
                            - 📋 Copy responses using the copy button on each message
                            - 👍👎 Like/dislike messages to provide feedback
                            
                            **Configuration:**
                            
                            To customize settings like chunk size, embedding model, or LLM parameters, 
                            edit the `config.yaml` file in the project root and restart the application.
                            """
                        )

            # Event handlers
            async def add_message(history, message):
                """Add user message with files to chat history."""
                try:
                    logger.info(f"add_message called with message type: {type(message)}")
                    logger.info(f"Message content: {message}")

                    # Handle uploaded files
                    if message.get("files"):
                        logger.info(f"Processing {len(message['files'])} files")
                        for idx, file_path in enumerate(message["files"]):
                            logger.info(f"File {idx}: type={type(file_path)}, value={file_path}")
                            try:
                                # Upload file to backend
                                upload_result = await self.upload_file(file_path)
                                # Show file upload in chat
                                file_name = (
                                    file_path.split("/")[-1]
                                    if isinstance(file_path, str)
                                    else str(file_path)
                                )
                                history.append(
                                    {
                                        "role": "user",
                                        "content": f"📎 Uploaded: {file_name}\n\n{upload_result}",
                                    }
                                )
                            except Exception:
                                import traceback

                                error_traceback = traceback.format_exc()
                                logger.error(
                                    f"Error processing file {file_path}:\n{error_traceback}"
                                )
                                history.append(
                                    {
                                        "role": "user",
                                        "content": f"❌ Error uploading {file_path}:\n```\n{error_traceback}\n```",
                                    }
                                )

                    # Handle text message
                    if message.get("text"):
                        logger.info(f"Adding text message: {message['text'][:100]}...")
                        history.append({"role": "user", "content": message["text"]})

                    return history, gr.MultimodalTextbox(value=None, interactive=False)

                except Exception:
                    import traceback

                    error_traceback = traceback.format_exc()
                    logger.error(f"Error in add_message:\n{error_traceback}")
                    history.append(
                        {
                            "role": "user",
                            "content": f"❌ Error processing message:\n```\n{error_traceback}\n```",
                        }
                    )
                    return history, gr.MultimodalTextbox(value=None, interactive=False)

            async def bot_response(history):
                """Generate streaming bot response."""
                if not history or history[-1]["role"] != "user":
                    yield history
                    return

                # Get the last user message
                user_message = history[-1]["content"]

                # Query backend
                response_text = await self.query_rag(user_message, history[:-1])

                # Add assistant message and stream response
                history.append({"role": "assistant", "content": ""})
                for char in response_text:
                    history[-1]["content"] += char
                    yield history
                    await asyncio.sleep(0.01)

            # Connect events - chat input with multimodal support
            chat_msg = chat_input.submit(add_message, [chatbot, chat_input], [chatbot, chat_input])
            bot_msg = chat_msg.then(bot_response, chatbot, chatbot, api_name="bot_response")
            bot_msg.then(lambda: gr.MultimodalTextbox(interactive=True), None, [chat_input])

            # Wire up the built-in stop button to cancel ongoing generation
            chat_input.stop(fn=None, inputs=None, outputs=None, cancels=[chat_msg, bot_msg])

            # Like/dislike
            def handle_like(data: gr.LikeData):
                logger.info(f"{'Liked' if data.liked else 'Disliked'} message at {data.index}")

            chatbot.like(handle_like, None, None, like_user_message=True)

        return interface

    def launch(self) -> None:
        """
        Launch the Gradio interface.

        Uses Gradio's built-in server which handles async event handlers.
        """
        logger.info("Launching Gradio interface...")

        interface = self.create_interface()
        interface.launch(
            server_name=self.config.frontend.host,
            server_port=self.config.frontend.port,
            share=self.config.frontend.share,
        )


def main():
    """Main entry point for the frontend."""
    config = load_config()

    # Setup logging
    from rag.logging_config import setup_logging

    setup_logging(config)

    # Create and launch interface
    chat_interface = RAGChatInterface(config)
    chat_interface.launch()


if __name__ == "__main__":
    main()
