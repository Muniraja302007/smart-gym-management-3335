from app.db.mongodb import get_database
from langchain.chat_models import ChatOpenAI
from config import settings
import json
import logging
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

class DietPlanner:
    """
    AI-powered nutrition and diet planner
    Creates personalized meal plans based on fitness goals
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.db = get_database()
    
    async def calculate_tdee(self, member_id: str) -> float:
        """
        Calculate Total Daily Energy Expenditure
        
        TDEE = BMR × Activity Factor
        """
        member = await self.db.members.find_one({'_id': ObjectId(member_id)})
        
        # Mifflin-St Jeor equation for BMR
        age = member.get('age', 30)
        weight = member.get('weight', 70)  # kg
        height = member.get('height', 175)  # cm
        gender = member.get('gender', 'M')
        
        if gender.lower() == 'M':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Activity factor
        fitness_level = member.get('fitness_level', 'sedentary')
        activity_factors = {
            'sedentary': 1.2,
            'light': 1.375,
            'moderate': 1.55,
            'intense': 1.725,
            'very_intense': 1.9
        }
        
        activity_factor = activity_factors.get(fitness_level, 1.55)
        tdee = bmr * activity_factor
        
        return tdee
    
    async def generate_meal_plan(self, member_id: str, days: int = 7) -> dict:
        """
        Generate personalized meal plan
        """
        try:
            member = await self.db.members.find_one({'_id': ObjectId(member_id)})
            
            if not member:
                raise ValueError(f"Member {member_id} not found")
            
            # Calculate TDEE and caloric target
            tdee = await self.calculate_tdee(member_id)
            
            # Adjust based on goals
            goals = member.get('goals', [])
            if 'weight_loss' in goals:
                daily_calories = tdee - 500  # 500 calorie deficit
            elif 'muscle_gain' in goals:
                daily_calories = tdee + 300  # 300 calorie surplus
            else:
                daily_calories = tdee  # Maintenance
            
            # Create prompt
            prompt = self._create_diet_prompt(member, daily_calories, days)
            
            # Generate plan
            response = self.llm.invoke(prompt)
            plan_data = json.loads(response.content)
            
            # Save to database
            diet_doc = {
                'member_id': ObjectId(member_id),
                'daily_calories': daily_calories,
                'tdee': tdee,
                'macro_targets': plan_data.get('macro_targets', {}),
                'meals': plan_data.get('meals', []),
                'shopping_list': plan_data.get('shopping_list', []),
                'dietary_restrictions': member.get('dietary_restrictions', []),
                'created_at': datetime.utcnow(),
                'last_updated': datetime.utcnow()
            }
            
            result = await self.db.diet_plans.insert_one(diet_doc)
            diet_doc['_id'] = str(result.inserted_id)
            
            logger.info(f"Diet plan generated for member {member_id}")
            return diet_doc
        except Exception as e:
            logger.error(f"Diet plan generation failed: {e}")
            raise
    
    def _create_diet_prompt(self, member: dict, daily_calories: float, days: int) -> str:
        """
        Create prompt for diet plan generation
        """
        return f"""
        Create a {days}-day meal plan for a member with:
        
        Age: {member.get('age', 'N/A')}
        Weight: {member.get('weight', 'N/A')} kg
        Goal: {', '.join(member.get('goals', []))}
        Dietary Restrictions: {', '.join(member.get('dietary_restrictions', ['none']))}
        Allergies: {', '.join(member.get('allergies', ['none']))}
        Daily Calorie Target: {daily_calories:.0f} kcal
        
        Generate a {days}-day meal plan with:
        - Breakfast, lunch, dinner, and snacks
        - Macro breakdown for each meal
        - Total daily macros and calories
        - Shopping list for all ingredients
        - Meal prep instructions
        
        Return as JSON:
        {{
            "daily_target": {{
                "calories": {daily_calories:.0f},
                "protein_g": {daily_calories * 0.30 / 4:.0f},
                "carbs_g": {daily_calories * 0.45 / 4:.0f},
                "fat_g": {daily_calories * 0.25 / 9:.0f}
            }},
            "meals": [
                {{
                    "day": 1,
                    "meal_type": "Breakfast",
                    "items": ["item1", "item2"],
                    "calories": 500,
                    "macros": {{}}
                }}
            ],
            "shopping_list": ["item1", "item2"],
            "prep_instructions": "..."
        }}
        """
    
    async def log_meal(self, member_id: str, meal_data: dict) -> dict:
        """
        Log consumed meal
        """
        try:
            meal_log = {
                'member_id': ObjectId(member_id),
                'date': datetime.utcnow(),
                'meal_type': meal_data.get('meal_type'),
                'items': meal_data.get('items', []),
                'calories': meal_data.get('calories', 0),
                'macros': meal_data.get('macros', {}),
                'notes': meal_data.get('notes', '')
            }
            
            result = await self.db.nutrition_logs.insert_one(meal_log)
            logger.info(f"Meal logged for member {member_id}")
            return {'_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Meal logging failed: {e}")
            raise
