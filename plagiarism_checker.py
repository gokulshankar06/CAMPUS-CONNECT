"""
Simple Plagiarism Detection Utility
CampusConnect+ Event Management System
"""

import re
import hashlib
from difflib import SequenceMatcher
from collections import Counter
import sqlite3
from models import get_db_connection

class PlagiarismChecker:
    def __init__(self):
        self.min_similarity_threshold = 0.7  # 70% similarity
        self.min_phrase_length = 5  # Minimum words in a phrase to check
        
    def normalize_text(self, text):
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation but keep word boundaries
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra spaces
        text = text.strip()
        return text
    
    def extract_phrases(self, text, phrase_length=5):
        """Extract overlapping phrases of specified length"""
        words = text.split()
        phrases = []
        
        for i in range(len(words) - phrase_length + 1):
            phrase = ' '.join(words[i:i + phrase_length])
            phrases.append(phrase)
        
        return phrases
    
    def calculate_similarity(self, text1, text2):
        """Calculate similarity between two texts using SequenceMatcher"""
        normalized_text1 = self.normalize_text(text1)
        normalized_text2 = self.normalize_text(text2)
        
        return SequenceMatcher(None, normalized_text1, normalized_text2).ratio()
    
    def check_phrase_overlap(self, text1, text2, phrase_length=5):
        """Check for overlapping phrases between two texts"""
        phrases1 = set(self.extract_phrases(self.normalize_text(text1), phrase_length))
        phrases2 = set(self.extract_phrases(self.normalize_text(text2), phrase_length))
        
        if not phrases1 or not phrases2:
            return 0.0
        
        common_phrases = phrases1.intersection(phrases2)
        overlap_ratio = len(common_phrases) / min(len(phrases1), len(phrases2))
        
        return overlap_ratio
    
    def check_against_database(self, text, event_id, exclude_submission_id=None):
        """Check text against existing submissions in the database"""
        conn = get_db_connection()
        
        # Get all other submissions for the same event
        query = """
            SELECT id, title, abstract_text, user_id 
            FROM abstract_submissions 
            WHERE event_id = ? AND is_latest_version = 1
        """
        params = [event_id]
        
        if exclude_submission_id:
            query += " AND id != ?"
            params.append(exclude_submission_id)
        
        submissions = conn.execute(query, params).fetchall()
        conn.close()
        
        max_similarity = 0.0
        max_phrase_overlap = 0.0
        similar_submission = None
        
        for submission in submissions:
            # Check title similarity
            title_similarity = self.calculate_similarity(text, submission['title'])
            
            # Check abstract similarity
            abstract_similarity = self.calculate_similarity(text, submission['abstract_text'])
            
            # Check phrase overlap
            phrase_overlap = self.check_phrase_overlap(text, submission['abstract_text'])
            
            # Use the maximum similarity found
            current_similarity = max(title_similarity, abstract_similarity)
            
            if current_similarity > max_similarity:
                max_similarity = current_similarity
                similar_submission = submission
            
            if phrase_overlap > max_phrase_overlap:
                max_phrase_overlap = phrase_overlap
        
        # Combine similarity metrics (weighted average)
        combined_score = (max_similarity * 0.7) + (max_phrase_overlap * 0.3)
        
        return {
            'similarity_score': combined_score,
            'text_similarity': max_similarity,
            'phrase_overlap': max_phrase_overlap,
            'similar_submission': similar_submission,
            'is_suspicious': combined_score > self.min_similarity_threshold
        }
    
    def check_common_phrases(self, text):
        """Check for overly common academic phrases"""
        common_phrases = [
            "in this paper we",
            "the purpose of this study",
            "our research shows",
            "the results indicate",
            "in conclusion",
            "this study aims to",
            "the main objective",
            "our findings suggest",
            "previous research has shown",
            "it is important to note"
        ]
        
        normalized_text = self.normalize_text(text)
        phrase_count = 0
        
        for phrase in common_phrases:
            if phrase in normalized_text:
                phrase_count += 1
        
        # Return ratio of common phrases found
        return phrase_count / len(common_phrases)
    
    def generate_report(self, text, event_id, exclude_submission_id=None):
        """Generate a comprehensive plagiarism report"""
        db_check = self.check_against_database(text, event_id, exclude_submission_id)
        common_phrases_ratio = self.check_common_phrases(text)
        
        # Calculate overall risk score
        risk_factors = [
            db_check['similarity_score'] * 0.6,  # Database similarity (highest weight)
            common_phrases_ratio * 0.2,          # Common phrases
            (len(text.split()) < 50) * 0.2       # Very short text penalty
        ]
        
        overall_risk = sum(risk_factors)
        
        # Determine risk level
        if overall_risk > 0.8:
            risk_level = "HIGH"
        elif overall_risk > 0.5:
            risk_level = "MEDIUM"
        elif overall_risk > 0.3:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"
        
        report = {
            'overall_score': overall_risk,
            'risk_level': risk_level,
            'database_similarity': db_check['similarity_score'],
            'text_similarity': db_check['text_similarity'],
            'phrase_overlap': db_check['phrase_overlap'],
            'common_phrases_ratio': common_phrases_ratio,
            'similar_submission': db_check['similar_submission'],
            'is_suspicious': overall_risk > 0.5,
            'recommendations': self._generate_recommendations(overall_risk, db_check)
        }
        
        return report
    
    def _generate_recommendations(self, overall_risk, db_check):
        """Generate recommendations based on plagiarism check results"""
        recommendations = []
        
        if overall_risk > 0.8:
            recommendations.append("URGENT: Manual review required - high similarity detected")
            recommendations.append("Consider rejecting or requesting major revision")
        elif overall_risk > 0.5:
            recommendations.append("Manual review recommended - moderate similarity detected")
            recommendations.append("Request clarification or minor revision")
        elif overall_risk > 0.3:
            recommendations.append("Low risk detected - brief review suggested")
        else:
            recommendations.append("Minimal plagiarism risk - safe to approve")
        
        if db_check['similar_submission']:
            recommendations.append(f"Similar content found in submission ID: {db_check['similar_submission']['id']}")
        
        return recommendations

# Utility functions for easy integration
def check_abstract_plagiarism(abstract_text, event_id, submission_id=None):
    """Quick function to check abstract for plagiarism"""
    checker = PlagiarismChecker()
    return checker.generate_report(abstract_text, event_id, submission_id)

def update_submission_plagiarism_score(submission_id, plagiarism_score, plagiarism_status='clean'):
    """Update plagiarism score in database"""
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE abstract_submissions 
            SET plagiarism_score = ?, plagiarism_status = ?
            WHERE id = ?
        """, (plagiarism_score, plagiarism_status, submission_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating plagiarism score: {e}")
        return False
    finally:
        conn.close()

def batch_check_plagiarism(event_id):
    """Check all submissions for an event for plagiarism"""
    conn = get_db_connection()
    
    submissions = conn.execute("""
        SELECT id, abstract_text FROM abstract_submissions 
        WHERE event_id = ? AND is_latest_version = 1 AND plagiarism_status = 'pending'
    """, (event_id,)).fetchall()
    
    conn.close()
    
    checker = PlagiarismChecker()
    results = []
    
    for submission in submissions:
        try:
            report = checker.generate_report(
                submission['abstract_text'], 
                event_id, 
                submission['id']
            )
            
            # Update database with results
            status = 'flagged' if report['is_suspicious'] else 'clean'
            update_submission_plagiarism_score(
                submission['id'], 
                report['overall_score'], 
                status
            )
            
            results.append({
                'submission_id': submission['id'],
                'report': report
            })
            
        except Exception as e:
            print(f"Error checking submission {submission['id']}: {e}")
            continue
    
    return results

if __name__ == "__main__":
    # Example usage
    checker = PlagiarismChecker()
    
    sample_text = """
    This paper presents a novel approach to machine learning in educational environments. 
    Our research shows that implementing AI-driven personalized learning systems can 
    significantly improve student outcomes. The main objective of this study is to 
    demonstrate the effectiveness of adaptive learning algorithms.
    """
    
    # This would require a real event_id from your database
    # report = checker.generate_report(sample_text, 1)
    # print("Plagiarism Report:", report)
