from app.db.mongodb import get_database
from langchain.chat_models import ChatOpenAI
from config import settings
import json
import logging
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

class WorkoutGenerator:
    """
    AI-powered workout plan generator using LLM
    Creates personalized workout plans based on member profile
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.db = get_database()
    
    async def generate_workout_plan(self, member_id: str) -> dict:
        """
        Generate personalized workout plan
        
        Considers:
        - Age, weight, height, gender
        - Fitness level
        - Goals (muscle gain, weight loss, strength, endurance)
        - Available equipment
        - Time availability
        - Injuries/limitations
        """
        try:
            # Fetch member profile
            member = await self.db.members.find_one({'_id': ObjectId(member_id)})
            
            if not member:
                raise ValueError(f"Member {member_id} not found")
            
            # Create prompt
            prompt = self._create_workout_prompt(member)
            
            # Generate workout using LLM
            response = self.llm.invoke(prompt)
            
            # Parse response
            workout_data = json.loads(response.content)
            
            # Save to database
            workout_doc = {
                'member_id': ObjectId(member_id),
                'ai_generated': True,
                'workouts': workout_data['workouts'],
                'progression': workout_data.get('progression', ''),
                'rest_days': workout_data.get('rest_days', []),
                'created_at': datetime.utcnow(),
                'last_updated': datetime.utcnow()
            }
            
            result = await self.db.workout_plans.insert_one(workout_doc)
            workout_doc['_id'] = str(result.inserted_id)
            
            logger.info(f"Workout plan generated for member {member_id}")
            return workout_doc
        except Exception as e:
            logger.error(f"Workout generation failed: {e}")
            raise
    
    def _create_workout_prompt(self, member: dict) -> str:
        """
        Create detailed prompt for workout generation
        """
        return f"""
        Create a personalized 4-week workout plan for a member with these details:
        
        Age: {member.get('age', 'N/A')}
        Weight: {member.get('weight', 'N/A')} kg
        Height: {member.get('height', 'N/A')} cm
        Gender: {member.get('gender', 'N/A')}
        Fitness Level: {member.get('fitness_level', 'beginner')}
        Goals: {', '.join(member.get('goals', []))}
        Available Equipment: {', '.join(member.get('equipment', ['dumbbells', 'barbells', 'machines']))}
        
        Generate a detailed 7-day workout split with:
        - Specific exercises with sets, reps, and rest periods
        - Clear progression strategy
        - Rest day recommendations
        - Intensity adjustments for each week
        
        Return as JSON with structure:
        {{
            "workouts": [
                {{
                    "day": "Monday",
                    "type": "Chest & Triceps",
                    "duration": 60,
                    "intensity": "High",
                    "exercises": [
                        {{
                            "name": "Exercise name",
                            "sets": 4,
                            "reps": 8,
                            "weight_kg": 100,
                            "rest_seconds": 120,
                            "notes": "Form tips"
                        }}
                    ]
                }}
            ],
            "rest_days": ["Wednesday", "Sunday"],
            "progression": "Increase weight by 2.5kg weekly"
        }}
        """
    
    async def adjust_workout_plan(self, member_id: str, feedback: str) -> dict:
        """
        Adjust workout plan based on member feedback
        """
        try:
            # Get current plan
            current_plan = await self.db.workout_plans.find_one(
                {'member_id': ObjectId(member_id)},
                sort=[('created_at', -1)]
            )
            
            if not current_plan:
                raise ValueError("No existing workout plan found")
            
            # Create adjustment prompt
            prompt = f"""
            Adjust the following workout plan based on this feedback:
            
            Current Plan: {json.dumps(current_plan['workouts'])}
            
            Member Feedback: {feedback}
            
            Provide adjustments that address the feedback while maintaining 
            progressive overload and program coherence.
            """
            
            # Generate adjustment
            response = self.llm.invoke(prompt)
            adjusted_data = json.loads(response.content)
            
            # Update database
            await self.db.workout_plans.update_one(
                {'_id': current_plan['_id']},
                {
                    '$set': {
                        'workouts': adjusted_data['workouts'],
                        'last_updated': datetime.utcnow(),
                        'adjustment_reason': feedback
                    }
                }
            )
            
            logger.info(f"Workout plan adjusted for member {member_id}")
            return adjusted_data
        except Exception as e:
            logger.error(f"Workout adjustment failed: {e}")
            raise
