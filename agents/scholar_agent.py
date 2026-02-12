# agents/scholar_agent.py
import os
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from core.tools.library_tools import LIBRARY_TOOLS
from agents.prompts import SCHOLAR_BOT_SYSTEM_PROMPT
from core.utils.logging_utils import get_logger
import operator

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

_log = get_logger(__name__)


def _user_facing_error(exc: Exception) -> str:
    """Return a short, actionable message for known API errors."""
    msg = str(exc).lower()
    if "429" in str(exc) or "insufficient_quota" in msg or "quota" in msg or "rate_limit" in msg:
        return (
            "Usage or rate limit reached. Check your provider's billing/limits "
            "(Groq: https://console.groq.com  or OpenAI: https://platform.openai.com/account/billing) "
            "or try again later."
        )
    if "401" in str(exc) or "invalid_api_key" in msg or "authentication" in msg:
        return (
            "Invalid or missing API key. Set GROQ_API_KEY (for Groq) or OPENAI_API_KEY (for OpenAI) in your .env file. "
            "Groq: https://console.groq.com/keys  |  OpenAI: https://platform.openai.com/api-keys"
        )
    if "404" in str(exc) or "model_not_found" in msg:
        return (
            "The selected model isn't available. Set GROQ_MODEL (e.g. llama-3.1-8b-instant) or "
            "OPENAI_MODEL (e.g. gpt-4o-mini) in .env depending on your provider."
        )
    return f"Something went wrong: {exc}. Please try again or rephrase your question."


# Define the state for our agent
class AgentState(TypedDict):
    """State for the Scholar agent."""
    messages: Annotated[Sequence[BaseMessage], operator.add]


class ScholarAgent:
    """
    LangGraph-based conversational agent for library search.
    
    Features:
    - Stateful conversations with context retention
    - Natural language parameter extraction
    - Intelligent tool calling for library searches
    - Multi-turn dialogue support
    """
    
    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.7,
        system_prompt: str = SCHOLAR_BOT_SYSTEM_PROMPT,
        provider: str | None = None,
    ):
        """
        Initialize the Scholar agent.

        Args:
            model_name: Model to use (e.g. llama-3.1-8b-instant for Groq, gpt-4o-mini for OpenAI).
                        Defaults from GROQ_MODEL or OPENAI_MODEL per provider.
            temperature: Model temperature for response generation
            system_prompt: System prompt defining agent behavior
            provider: "groq" or "openai". Defaults to env LLM_PROVIDER, then "groq".
        """
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        if model_name is None:
            model_name = (
                os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
                if provider == "groq"
                else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            )
        _log.info(f"Initializing ScholarAgent with provider={provider}, model={model_name}")

        if provider == "groq":
            if ChatGroq is None:
                raise ImportError("Groq provider requested but langchain-groq is not installed. Run: pip install langchain-groq")
            self.llm = ChatGroq(
                model=model_name,
                temperature=temperature,
                streaming=True,
            ).bind_tools(LIBRARY_TOOLS)
        else:
            self.llm = ChatOpenAI(
                model=model_name,
                temperature=temperature,
                streaming=True,
            ).bind_tools(LIBRARY_TOOLS)
        
        self.system_prompt = system_prompt
        
        # Create the graph
        self.graph = self._create_graph()
        
        # Initialize memory for stateful conversations
        self.memory = MemorySaver()
        
        # Compile the graph with memory
        self.app = self.graph.compile(checkpointer=self.memory)
        
        _log.info("ScholarAgent initialized successfully")
    
    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow."""
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(LIBRARY_TOOLS))
        
        # Define the flow
        workflow.set_entry_point("agent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
        # After tools, go back to agent
        workflow.add_edge("tools", "agent")
        
        return workflow
    
    def _call_model(self, state: AgentState) -> AgentState:
        """
        Call the LLM with the current state.
        
        Args:
            state: Current agent state with messages
            
        Returns:
            Updated state with new message
        """
        messages = state["messages"]
        
        # Add system prompt if this is the start
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=self.system_prompt)] + list(messages)
        
        _log.info(f"Calling LLM with {len(messages)} messages")
        response = self.llm.invoke(messages)
        
        return {"messages": [response]}
    
    def _should_continue(self, state: AgentState) -> str:
        """
        Determine if we should call tools or end.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" to call tools, "end" to finish
        """
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are tool calls, continue
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            _log.info(f"Tool calls detected: {len(last_message.tool_calls)}")
            return "continue"
        
        # Otherwise end
        _log.info("No tool calls, ending")
        return "end"
    
    def chat(self, user_input: str, thread_id: str = "default") -> str:
        """
        Process a user message and return the agent's response.
        
        Args:
            user_input: User's message
            thread_id: Thread ID for conversation tracking (enables stateful conversations)
            
        Returns:
            Agent's response text
        """
        _log.info(f"Processing user input (thread: {thread_id}): {user_input[:100]}...")
        
        try:
            # Create the input state
            input_state = {
                "messages": [HumanMessage(content=user_input)]
            }
            
            # Configure with thread ID for memory
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke the agent
            result = self.app.invoke(input_state, config)
            messages = result["messages"]

            # Include any tool results from this turn so the user always sees search results
            # (the LLM sometimes replies with only a follow-up question and omits the results)
            last_human_idx = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), None)
            tool_parts = []
            if last_human_idx is not None:
                for m in messages[last_human_idx + 1 :]:
                    if isinstance(m, ToolMessage) and getattr(m, "content", None):
                        tool_parts.append(m.content)

            final_message = messages[-1]
            if isinstance(final_message, AIMessage):
                response = (final_message.content or "").strip()
            else:
                response = str(final_message).strip()

            if tool_parts:
                response = "\n\n".join(tool_parts) + ("\n\n---\n\n" + response if response else "")
            _log.info(f"Agent response: {response[:100]}...")
            return response
            
        except Exception as e:
            _log.exception("Error processing message")
            return _user_facing_error(e)
    
    def stream_chat(self, user_input: str, thread_id: str = "default"):
        """
        Stream the agent's response token by token.
        
        Args:
            user_input: User's message
            thread_id: Thread ID for conversation tracking
            
        Yields:
            Response tokens as they're generated
        """
        _log.info(f"Streaming response for input (thread: {thread_id}): {user_input[:100]}...")
        
        try:
            # Create the input state
            input_state = {
                "messages": [HumanMessage(content=user_input)]
            }
            
            # Configure with thread ID for memory
            config = {"configurable": {"thread_id": thread_id}}
            
            # Stream the response
            for chunk in self.app.stream(input_state, config):
                # Extract messages from the chunk
                if "agent" in chunk:
                    messages = chunk["agent"].get("messages", [])
                    if messages:
                        message = messages[-1]
                        if isinstance(message, AIMessage) and message.content:
                            yield message.content
                        
        except Exception as e:
            _log.exception("Error streaming response")
            yield _user_facing_error(e)
    
    def reset_conversation(self, thread_id: str = "default"):
        """
        Reset the conversation history for a thread.
        
        Args:
            thread_id: Thread ID to reset
        """
        _log.info(f"Resetting conversation for thread: {thread_id}")
        # Note: MemorySaver doesn't have a direct clear method
        # The conversation is effectively reset by using a new thread_id
        pass


# Factory function for easy instantiation
def create_scholar_agent(
    model_name: str | None = None,
    temperature: float | None = None,
    provider: str | None = None,
) -> ScholarAgent:
    """
    Create a ScholarAgent instance.

    Args:
        model_name: Override model (defaults from GROQ_MODEL or OPENAI_MODEL per provider).
        temperature: Model temperature (defaults from OPENAI_TEMPERATURE or 0.7).
        provider: "groq" or "openai" (defaults from LLM_PROVIDER env, then "groq").

    Returns:
        Initialized ScholarAgent
    """
    if temperature is None:
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    return ScholarAgent(model_name=model_name, temperature=temperature, provider=provider)
