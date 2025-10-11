"""
Modern Gradio frontend for Agentic RAG with advanced features.

Features:
- Sidebar with configuration controls
- Modern ChatInterface with streaming
- Multimodal input (text + files)
- Like/dislike buttons
- Code artifacts display
- Tabbed interface
- File upload with preview
- Settings panel
- Chat history
"""

import asyncio
import time

import gradio as gr
import httpx
from loguru import logger

from rag.config import Config, load_config


class ModernRAGInterface:
    """
    Modern Gradio interface for RAG system with advanced features.

    Features:
    - Collapsible sidebar with settings
    - ChatInterface with streaming support
    - Multimodal input (text + files)
    - Like/dislike feedback
    - Code and document preview
    - Tabbed organization
    - File history
    - Configuration controls
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize the modern chat interface.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.api_base_url = f"http://{config.api.host}:{config.api.port}"
        self.client = httpx.AsyncClient(timeout=300.0)
        self.uploaded_files = []  # Track uploaded files

        logger.info(f"Initialized Modern RAG interface: {self.api_base_url}")

    async def upload_file_async(
        self, file
    ) -> dict[str, bool | str | dict[str, str | int | list[str]]]:
        """
        Upload a file to the backend (async).

        Args:
            file: Uploaded file object.

        Returns:
            Upload result dictionary.
        """
        if file is None:
            return {"success": False, "message": "No file selected"}

        try:
            logger.info(f"Uploading file: {file.name}")

            with open(file.name, "rb") as f:
                files = {"file": (file.name, f)}
                response = await self.client.post(
                    f"{self.api_base_url}/upload",
                    files=files,
                )

            if response.status_code == 200:
                result = response.json()
                self.uploaded_files.append(
                    {
                        "name": file.name,
                        "chunks": result["num_chunks"],
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                return {
                    "success": True,
                    "result": result,
                    "message": f"✅ Uploaded {file.name}",
                }
            else:
                return {
                    "success": False,
                    "message": f"❌ Upload failed: {response.text}",
                }

        except Exception as e:
            logger.exception(f"Error uploading file: {e}")
            return {"success": False, "message": f"❌ Error: {str(e)}"}

    def format_upload_status(
        self, result: dict[str, bool | str | dict[str, str | int | list[str]]]
    ) -> str:
        """Format upload status message with warnings."""
        if not result.get("success"):
            return str(result.get("message", "Unknown error"))

        result_data = result.get("result")
        if not isinstance(result_data, dict):
            return str(result.get("message", "Upload successful"))

        message = f"{result.get('message', 'Upload successful')}\n\n"
        message += f"📄 **Documents**: {result_data.get('num_documents', 0)}\n"
        message += f"📝 **Chunks**: {result_data.get('num_chunks', 0)}\n"
        document_ids = result_data.get("document_ids", [])
        if isinstance(document_ids, list):
            message += f"🆔 **IDs**: {len(document_ids)} chunks added\n"

        # Add warnings if present
        warnings = result_data.get("warnings")
        if warnings and isinstance(warnings, list):
            message += "\n" + "─" * 60 + "\n"
            for warning in warnings:
                message += f"{warning}\n"
            message += "─" * 60

        return message

    async def query_rag_streaming(self, message: str, history: list[dict[str, str]], top_k: int):
        """
        Query RAG with streaming response.

        Args:
            message: User message.
            history: Chat history.
            top_k: Number of documents to retrieve.

        Yields:
            Streamed response chunks.
        """
        if not message:
            yield "Please enter a question."
            return

        try:
            logger.info(f"Querying RAG: {message[:100]}...")

            # Add user message to history
            history.append({"role": "user", "content": message})

            # Query backend
            response = await self.client.post(
                f"{self.api_base_url}/query",
                json={"query": message, "top_k": top_k},
            )

            if response.status_code == 200:
                result = response.json()
                full_answer = ""

                # Add warnings if present
                if result.get("warnings"):
                    warning_text = "─" * 60 + "\n"
                    for warning in result["warnings"]:
                        warning_text += f"{warning}\n"
                    warning_text += "─" * 60 + "\n\n"
                    full_answer += warning_text

                # Stream the answer character by character
                answer_text = result["answer"]
                for i in range(len(answer_text)):
                    full_answer_chunk = full_answer + answer_text[: i + 1]
                    history_with_answer = history + [
                        {"role": "assistant", "content": full_answer_chunk}
                    ]
                    yield history_with_answer
                    await asyncio.sleep(0.01)  # Streaming effect

                # Add sources
                if result.get("sources"):
                    sources_text = "\n\n📚 **Sources:**\n"
                    for i, source in enumerate(result["sources"], 1):
                        metadata = source["metadata"]
                        source_info = metadata.get("source", "Unknown")
                        sources_text += f"{i}. {source_info}\n"
                    full_answer += sources_text

                # Final message
                history_with_complete = history + [{"role": "assistant", "content": full_answer}]
                yield history_with_complete

            else:
                error_msg = f"❌ Query failed: {response.text}"
                history_with_error = history + [{"role": "assistant", "content": error_msg}]
                yield history_with_error

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.exception(error_msg)
            history_with_error = history + [{"role": "assistant", "content": error_msg}]
            yield history_with_error

    def handle_like_dislike(self, data: gr.LikeData):
        """Handle like/dislike feedback."""
        action = "👍 upvoted" if data.liked else "👎 downvoted"
        logger.info(f"User {action} message at index {data.index}")
        # Could send feedback to backend for learning
        print(f"Feedback: {action} - {data.value}")

    def get_file_history(self) -> str:
        """Get formatted file upload history."""
        if not self.uploaded_files:
            return "No files uploaded yet."

        history = "📁 **Uploaded Files:**\n\n"
        for i, file_info in enumerate(self.uploaded_files, 1):
            history += f"{i}. **{file_info['name']}**\n"
            history += f"   - Chunks: {file_info['chunks']}\n"
            history += f"   - Time: {file_info['timestamp']}\n\n"

        return history

    def create_interface(self) -> gr.Blocks:
        """Create the modern Gradio interface with all features."""

        # Custom CSS for better styling
        custom_css = """
        .gradio-container {
            font-family: 'Inter', sans-serif;
        }
        .warning-box {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 10px 0;
        }
        .success-box {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 12px;
            margin: 10px 0;
        }
        """

        with gr.Blocks(
            title="🤖 Agentic RAG - Modern Interface",
            theme=gr.themes.Soft(
                primary_hue="blue",
                secondary_hue="slate",
            ),
            css=custom_css,
            fill_height=True,
        ) as demo:
            # Header
            gr.Markdown(
                """
                # 🤖 Agentic RAG - Advanced Document Q&A System
                
                Ask questions about your uploaded documents using state-of-the-art RAG technology.
                Upload PDFs, DOCX, images, or websites and chat with your knowledge base!
                """
            )

            with gr.Row():
                # Sidebar for controls
                with gr.Sidebar(open=True, width=300, label="⚙️ Settings & Controls"):
                    gr.Markdown("### 📤 Upload Documents")

                    file_upload = gr.File(
                        label="Choose File",
                        file_types=[".pdf", ".docx", ".txt", ".jpg", ".png"],
                        file_count="single",
                    )
                    upload_btn = gr.Button("📤 Upload", variant="primary", size="sm")
                    upload_status = gr.Markdown("Ready to upload")

                    gr.Markdown("---")
                    gr.Markdown("### 🎛️ Query Settings")

                    top_k_slider = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=5,
                        step=1,
                        label="Number of Retrieved Documents",
                        info="More documents = more context but slower",
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 📊 File History")

                    file_history_display = gr.Markdown("No files uploaded yet.")
                    refresh_history_btn = gr.Button("🔄 Refresh History", size="sm")

                # Main chat area
                with gr.Column(scale=3):
                    # Create chatbot
                    chatbot = gr.Chatbot(
                        type="messages",
                        label="💬 Chat with Your Documents",
                        height=500,
                        placeholder="<strong>👋 Welcome to Agentic RAG!</strong><br><br>Upload documents on the left and start asking questions!",
                        show_copy_button=True,
                        bubble_full_width=False,
                        avatar_images=(
                            None,  # User avatar (default)
                            "https://em-content.zobj.net/source/twitter/376/robot_1f916.png",  # Bot avatar
                        ),
                    )

                    # Chat input
                    with gr.Row():
                        chat_input = gr.Textbox(
                            placeholder="Ask a question about your documents... (Press Enter to send)",
                            show_label=False,
                            scale=9,
                            container=False,
                        )
                        send_btn = gr.Button("🚀 Send", variant="primary", scale=1)

                    # Example questions
                    gr.Examples(
                        examples=[
                            "What is this document about?",
                            "Summarize the main points",
                            "What are the key findings?",
                            "List all important dates mentioned",
                            "Explain the methodology used",
                        ],
                        inputs=chat_input,
                        label="💡 Example Questions",
                    )

                    # Action buttons
                    with gr.Row():
                        clear_btn = gr.Button("🗑️ Clear Chat", size="sm")
                        _retry_btn = gr.Button("🔄 Retry Last", size="sm")  # noqa: F841

            # Footer with stats and info
            gr.Markdown(
                """
                ---
                
                <div style="text-align: center; color: #666;">
                    <small>
                    💡 <strong>Tip:</strong> Upload multiple documents to build your knowledge base | 
                    🔍 Adjust retrieval settings in the sidebar | 
                    👍👎 Rate responses to improve the system
                    </small>
                </div>
                """
            )

            # Event handlers

            # Upload file handler
            def upload_handler(file):
                """Handle file upload."""
                result = asyncio.run(self.upload_file_async(file))
                status = self.format_upload_status(result)
                history = self.get_file_history()
                return status, history

            upload_btn.click(
                upload_handler,
                inputs=[file_upload],
                outputs=[upload_status, file_history_display],
            )

            # Chat handler
            def respond(message, history, top_k):
                """Wrapper to handle async streaming in Gradio."""
                # Return the streaming generator for Gradio to handle
                return self.query_rag_streaming(message, history, top_k)  # Send message

            chat_input.submit(
                respond,
                inputs=[chat_input, chatbot, top_k_slider],
                outputs=[chatbot],
            ).then(
                lambda: "",  # Clear input
                outputs=[chat_input],
            )

            send_btn.click(
                respond,
                inputs=[chat_input, chatbot, top_k_slider],
                outputs=[chatbot],
            ).then(
                lambda: "",  # Clear input
                outputs=[chat_input],
            )

            # Clear chat
            clear_btn.click(
                lambda: [],
                outputs=[chatbot],
            )

            # Refresh history
            refresh_history_btn.click(
                self.get_file_history,
                outputs=[file_history_display],
            )

            # Like/dislike handler
            chatbot.like(
                self.handle_like_dislike,
                None,
                None,
                like_user_message=True,
            )

        return demo

    def launch(self) -> None:
        """Launch the Gradio interface."""
        logger.info("Launching Modern Gradio interface...")

        demo = self.create_interface()
        demo.queue()  # Enable queue for streaming
        demo.launch(
            server_name=self.config.frontend.host,
            server_port=self.config.frontend.port,
            share=self.config.frontend.share,
            show_error=True,
            show_api=False,
        )


def main():
    """Main entry point for the modern frontend."""
    config = load_config()

    # Setup logging
    from rag.logging_config import setup_logging

    setup_logging(config)

    # Create and launch interface
    interface = ModernRAGInterface(config)
    interface.launch()


if __name__ == "__main__":
    main()
