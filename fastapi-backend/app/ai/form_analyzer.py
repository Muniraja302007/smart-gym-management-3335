import cv2
import numpy as np
from mediapipe import solutions
import logging
from datetime import datetime
from bson import ObjectId
from app.db.mongodb import get_database

logger = logging.getLogger(__name__)

class FormAnalyzer:
    """
    AI-powered exercise form analysis using MediaPipe
    Analyzes poses and provides posture feedback
    """
    
    def __init__(self):
        self.mp_pose = solutions.pose
        self.pose = solutions.pose.Pose()
        self.db = get_database()
        self.exercise_standards = self._load_exercise_standards()
    
    async def analyze_video(self, member_id: str, exercise_name: str, video_path: str) -> dict:
        """
        Analyze exercise form from video file
        """
        try:
            cap = cv2.VideoCapture(video_path)
            frame_count = 0
            landmarks_list = []
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Detect pose
                results = self.pose.process(rgb_frame)
                
                if results.pose_landmarks:
                    landmarks_list.append(results.pose_landmarks)
                    frame_count += 1
            
            cap.release()
            
            # Analyze form across all frames
            analysis = await self._analyze_landmarks(
                member_id, exercise_name, landmarks_list
            )
            
            return analysis
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            raise
    
    async def analyze_image(self, member_id: str, exercise_name: str, image_path: str) -> dict:
        """
        Analyze exercise form from single image
        """
        try:
            image = cv2.imread(image_path)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            results = self.pose.process(rgb_image)
            
            if not results.pose_landmarks:
                return {
                    'form_score': 0,
                    'feedback': ['Unable to detect pose in image'],
                    'safe_to_continue': False
                }
            
            # Analyze pose
            analysis = await self._analyze_single_pose(
                member_id, exercise_name, results.pose_landmarks
            )
            
            return analysis
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            raise
    
    async def _analyze_landmarks(self, member_id: str, exercise_name: str, landmarks_list: list) -> dict:
        """
        Analyze pose landmarks and provide feedback
        """
        # Exercise-specific analysis
        if exercise_name.lower() == 'squat':
            return await self._analyze_squat(landmarks_list)
        elif exercise_name.lower() == 'deadlift':
            return await self._analyze_deadlift(landmarks_list)
        elif exercise_name.lower() == 'bench_press':
            return await self._analyze_bench_press(landmarks_list)
        else:
            return await self._generic_analysis(landmarks_list)
    
    async def _analyze_single_pose(self, member_id: str, exercise_name: str, landmarks) -> dict:
        """
        Analyze single pose snapshot
        """
        feedback = []
        score = 100
        
        # Get key joints
        left_shoulder = landmarks.landmark[11]
        right_shoulder = landmarks.landmark[12]
        left_hip = landmarks.landmark[23]
        right_hip = landmarks.landmark[24]
        left_knee = landmarks.landmark[25]
        right_knee = landmarks.landmark[26]
        left_ankle = landmarks.landmark[27]
        right_ankle = landmarks.landmark[28]
        
        # Exercise-specific feedback
        if exercise_name.lower() == 'squat':
            # Check knee alignment
            knee_ankle_alignment = abs(left_knee.x - left_ankle.x)
            if knee_ankle_alignment > 0.15:
                feedback.append({
                    'issue': 'Knee not aligned with ankle',
                    'severity': 'high',
                    'tip': 'Keep knees directly over ankles'
                })
                score -= 15
            
            # Check forward lean
            forward_lean = left_shoulder.x - left_hip.x
            if forward_lean > 0.2:
                feedback.append({
                    'issue': 'Excessive forward lean',
                    'severity': 'medium',
                    'tip': 'Keep chest up and core engaged'
                })
                score -= 10
        
        # Save analysis
        analysis_doc = {
            'member_id': ObjectId(member_id),
            'exercise': exercise_name,
            'form_score': max(0, score),
            'feedback': feedback,
            'safe_to_continue': score >= 70,
            'timestamp': datetime.utcnow()
        }
        
        await self.db.form_analysis.insert_one(analysis_doc)
        
        return {
            'form_score': max(0, score),
            'feedback': feedback,
            'safe_to_continue': score >= 70,
            'confidence': 0.85
        }
    
    async def _analyze_squat(self, landmarks_list: list) -> dict:
        """Squat-specific analysis"""
        # TODO: Implement detailed squat analysis
        pass
    
    async def _analyze_deadlift(self, landmarks_list: list) -> dict:
        """Deadlift-specific analysis"""
        # TODO: Implement detailed deadlift analysis
        pass
    
    async def _analyze_bench_press(self, landmarks_list: list) -> dict:
        """Bench press-specific analysis"""
        # TODO: Implement detailed bench press analysis
        pass
    
    async def _generic_analysis(self, landmarks_list: list) -> dict:
        """Generic pose analysis"""
        # TODO: Implement generic analysis
        pass
    
    def _load_exercise_standards(self) -> dict:
        """
        Load exercise-specific form standards
        """
        return {
            'squat': {
                'knee_hip_alignment': 0.1,
                'forward_lean_max': 0.15,
                'depth_ratio': 0.6
            },
            'deadlift': {
                'back_angle_min': 30,
                'knee_position': 'forward'
            },
            'bench_press': {
                'scapula_retraction': True,
                'arm_angle': 75
            }
        }
