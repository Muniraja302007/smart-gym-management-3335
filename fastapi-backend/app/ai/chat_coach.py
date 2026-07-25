from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from app.db.mongodb import get_database
from config import settings
import logging
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

class AIChatCoach:
    """
    AI Chat Coach using LangChain and OpenAI
    Provides conversational fitness coaching
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.db = get_database()
    
    async def create_coach_prompt(self, member_id: str) -> PromptTemplate:
        """
        Create personalized prompt for the coach based on member profile
        """
        # Fetch member profile
        member = await self.db.members.find_one({'_id': ObjectId(member_id)})
        
        prompt_template = f"""
        You are an expert AI Fitness Coach for Smart Gym.
        
        Member Profile:
        - Name: {member.get('name', 'Member')}
        - Age: {member.get('age', 'N/A')}
        - Fitness Level: {member.get('fitness_level', 'beginner')}
        - Goals: {', '.join(member.get('goals', []))}
        
        Guidelines:
        1. Provide evidence-based fitness advice
        2. Be encouraging and motivational
        3. Consider their fitness level and goals
        4. Ask clarifying questions when needed
        5. Provide specific, actionable advice
        
        IMPORTANT: This is educational guidance, not medical advice.
        
        Current conversation:
        {{history}}
        Human: {{input}}
        AI Coach:
        """
        
        return PromptTemplate(
            input_variables=["history", "input"],
            template=prompt_template
        )
    
    async def chat(self, member_id: str, message: str) -> dict:
        """
        Process chat message and return AI response
        """
        try:
            # Get conversation history
            chat_history = await self._get_chat_history(member_id)
            
            # Create memory from history
            memory = ConversationBufferMemory()
            for msg in chat_history:
                if msg['role'] == 'user':
                    memory.chat_memory.add_user_message(msg['content'])
                else:
                    memory.chat_memory.add_ai_message(msg['content'])
            
            # Create prompt
            prompt = await self.create_coach_prompt(member_id)
            
            # Create conversation chain
            conversation = ConversationChain(
                llm=self.llm,
                memory=memory,
                prompt=prompt,
                verbose=False
            )
            
            # Get response
            response = conversation.run(input=message)
            
            # Save to chat history
            await self._save_chat_message(
                member_id=member_id,
                role='user',
                content=message
            )
            
            await self._save_chat_message(
                member_id=member_id,
                role='ai',
                content=response
            )
            
            return {
                'message': response,
                'member_id': member_id,
                'timestamp': datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
    
    async def _get_chat_history(self, member_id: str, limit: int = 10) -> list:
        """
        Get recent chat history for context
        """
        history = await self.db.chat_history.find_one(
            {'member_id': ObjectId(member_id)}
        )
        
        if history:
            return history['conversation'][-limit:]
        return []
    
    async def _save_chat_message(self, member_id: str, role: str, content: str):
        """
        Save chat message to database
        """
        await self.db.chat_history.update_one(
            {'member_id': ObjectId(member_id)},
            {
                '$push': {
                    'conversation': {
                        'role': role,
                        'content': content,
                        'timestamp': datetime.utcnow()
                    }
                }
            },
            upsert=True
        )
