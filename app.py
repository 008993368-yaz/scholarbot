# app.py
import streamlit as st
import os
from dotenv import load_dotenv
from agents.scholar_agent import create_scholar_agent
from core.utils.logging_utils import get_logger
import uuid

# Load environment variables
load_dotenv()

# Configure logging
_log = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="ScholarBot - CSUSB Library Assistant",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E40AF;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #64748B;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #E0F2FE;
        border-left: 4px solid #0EA5E9;
    }
    .bot-message {
        background-color: #F1F5F9;
        border-left: 4px solid #64748B;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    
    if "agent" not in st.session_state:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        
        with st.spinner("Initializing ScholarBot..."):
            try:
                st.session_state.agent = create_scholar_agent(
                    model_name=model_name,
                    temperature=temperature
                )
                _log.info("Agent initialized successfully")
            except Exception as e:
                st.error(f"Failed to initialize agent: {e}")
                _log.error(f"Agent initialization failed: {e}")
                st.stop()


def display_chat_history():
    """Display the chat history."""
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant", avatar="📚"):
                st.markdown(content)


def main():
    """Main application function."""
    # Header
    st.markdown('<div class="main-header">📚 ScholarBot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Your AI-Powered CSUSB Library Research Assistant</div>',
        unsafe_allow_html=True
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ About ScholarBot")
        st.markdown("""
        **ScholarBot** helps you find academic resources from the CSUSB library using natural language.
        
        **What I can do:**
        - 🔍 Search for articles, books, journals, and dissertations
        - 📅 Filter by publication date
        - 📝 Understand natural language queries
        - 💬 Have multi-turn conversations
        - 🎯 Refine searches based on your feedback
        
        **Example queries:**
        - "Find papers on machine learning"
        - "Show me recent articles about climate change"
        - "I need books on data science from 2020"
        - "Search for dissertations on neural networks"
        """)
        
        st.divider()
        
        # Model settings
        st.subheader("⚙️ Settings")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        st.info(f"**Model:** {model}")
        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()
        
        st.divider()
        
        # Stats
        st.subheader("📊 Conversation Stats")
        st.metric("Messages", len(st.session_state.messages))
        st.metric("Thread ID", st.session_state.thread_id[:8] + "...")
        
        st.divider()
        
        # Tips
        with st.expander("💡 Tips for Better Results"):
            st.markdown("""
            1. **Be specific**: Include keywords, authors, or topics
            2. **Use filters**: Mention resource types (articles, books) or date ranges
            3. **Refine searches**: Ask follow-up questions to narrow results
            4. **Natural language**: Just describe what you're looking for
            """)
    
    # Main chat interface
    st.divider()
    
    # Display chat history
    display_chat_history()
    
    # Chat input
    if prompt := st.chat_input("Ask me about library resources..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant", avatar="📚"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Stream the response
                with st.spinner("Thinking..."):
                    response = st.session_state.agent.chat(
                        prompt,
                        thread_id=st.session_state.thread_id
                    )
                    full_response = response
                    message_placeholder.markdown(full_response)
                
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                message_placeholder.markdown(error_msg)
                full_response = error_msg
                _log.error(f"Error getting response: {e}")
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        st.error("⚠️ OPENAI_API_KEY not found in environment variables. Please set it in your .env file.")
        st.stop()
    
    main()
