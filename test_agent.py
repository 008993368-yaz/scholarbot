# test_agent.py
"""
Manual testing script for ScholarBot agent.
Run this to test the agent functionality without the Streamlit UI.
"""
import os
from dotenv import load_dotenv
from agents.scholar_agent import create_scholar_agent
from core.utils.logging_utils import get_logger

# Load environment
load_dotenv()
_log = get_logger(__name__)


def test_basic_search():
    """Test basic search functionality."""
    print("\n" + "="*60)
    print("TEST 1: Basic Search")
    print("="*60)
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    
    query = "Find papers on machine learning"
    print(f"\nUser: {query}")
    response = agent.chat(query, thread_id="test1")
    print(f"\nBot: {response}\n")


def test_filtered_search():
    """Test search with filters."""
    print("\n" + "="*60)
    print("TEST 2: Filtered Search")
    print("="*60)
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    
    query = "Show me recent articles about climate change from 2023"
    print(f"\nUser: {query}")
    response = agent.chat(query, thread_id="test2")
    print(f"\nBot: {response}\n")


def test_multi_turn_conversation():
    """Test multi-turn conversation with context."""
    print("\n" + "="*60)
    print("TEST 3: Multi-turn Conversation")
    print("="*60)
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    thread_id = "test3"
    
    # First turn
    query1 = "I need research on neural networks"
    print(f"\nUser: {query1}")
    response1 = agent.chat(query1, thread_id=thread_id)
    print(f"\nBot: {response1}\n")
    
    # Second turn - should understand context
    query2 = "Show only books from the last 5 years"
    print(f"\nUser: {query2}")
    response2 = agent.chat(query2, thread_id=thread_id)
    print(f"\nBot: {response2}\n")


def test_clarifying_questions():
    """Test agent asking clarifying questions."""
    print("\n" + "="*60)
    print("TEST 4: Clarifying Questions")
    print("="*60)
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    
    # Vague query that should prompt clarification
    query = "Find papers by John Smith"
    print(f"\nUser: {query}")
    response = agent.chat(query, thread_id="test4")
    print(f"\nBot: {response}\n")


def test_resource_type_filter():
    """Test filtering by resource type."""
    print("\n" + "="*60)
    print("TEST 5: Resource Type Filter")
    print("="*60)
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    
    query = "Find dissertations on artificial intelligence"
    print(f"\nUser: {query}")
    response = agent.chat(query, thread_id="test5")
    print(f"\nBot: {response}\n")


def interactive_test():
    """Interactive testing mode."""
    print("\n" + "="*60)
    print("INTERACTIVE TEST MODE")
    print("="*60)
    print("\nType your queries (or 'quit' to exit)\n")
    
    agent = create_scholar_agent(model_name="gpt-4", temperature=0.7)
    thread_id = "interactive"
    
    while True:
        query = input("You: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break
        
        if not query:
            continue
        
        try:
            response = agent.chat(query, thread_id=thread_id)
            print(f"\nBot: {response}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


def run_all_tests():
    """Run all automated tests."""
    print("\n" + "="*80)
    print(" SCHOLARBOT TEST SUITE")
    print("="*80)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ ERROR: OPENAI_API_KEY not found in environment variables")
        print("Please set your API key in .env file\n")
        return
    
    try:
        test_basic_search()
        test_filtered_search()
        test_multi_turn_conversation()
        test_clarifying_questions()
        test_resource_type_filter()
        
        print("\n" + "="*80)
        print(" ALL TESTS COMPLETED")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_test()
    else:
        run_all_tests()
        
        # Offer interactive mode
        choice = input("\nWould you like to try interactive mode? (y/n): ").strip().lower()
        if choice == 'y':
            interactive_test()
