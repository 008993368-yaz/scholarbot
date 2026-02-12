# agents/scholar_agent.py
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from core.tools.library_tools import LIBRARY_TOOLS
from agents.prompts import SCHOLAR_BOT_SYSTEM_PROMPT
from core.utils.logging_utils import get_logger
import operator

_log = get_logger(__name__)


def _user_facing_error(exc: Exception) -> str:
    """Return a short, actionable message for known API errors."""
    msg = str(exc).lower()
    if "429" in str(exc) or "insufficient_quota" in msg or "quota" in msg:
        return (
            "Your OpenAI account has hit its usage or quota limit. "
            "Check your plan and billing at https://platform.openai.com/account/billing, "
            "or try again later if you're on a free tier."
        )
    if "401" in str(exc) or "invalid_api_key" in msg or "authentication" in msg:
        return (
            "Invalid or missing OpenAI API key. Set OPENAI_API_KEY in your .env file. "
            "Get a key at https://platform.openai.com/api-keys."
        )
    if "404" in str(exc) or "model_not_found" in msg:
        return (
            "The selected model isn't available for your account. "
            "Set OPENAI_MODEL in .env to a model you have access to (e.g. gpt-3.5-turbo or gpt-4o-mini)."
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
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        system_prompt: str = SCHOLAR_BOT_SYSTEM_PROMPT
    ):
        """
        Initialize the Scholar agent.
        
        Args:
            model_name: OpenAI model to use (gpt-4o-mini, gpt-4o, gpt-3.5-turbo, etc.)
            temperature: Model temperature for response generation
            system_prompt: System prompt defining agent behavior
        """
        _log.info(f"Initializing ScholarAgent with model: {model_name}")
        
        # Initialize the LLM with tools
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True
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
            
            # Extract the final message
            final_message = result["messages"][-1]
            
            if isinstance(final_message, AIMessage):
                response = final_message.content
            else:
                response = str(final_message)
            
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
    model_name: str = "gpt-4",
    temperature: float = 0.7
) -> ScholarAgent:
    """
    Create a ScholarAgent instance.
    
    Args:
        model_name: OpenAI model to use
        temperature: Model temperature
        
    Returns:
        Initialized ScholarAgent
    """
    return ScholarAgent(model_name=model_name, temperature=temperature)
