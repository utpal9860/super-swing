"""
Web-based pattern review interface
Allows manual labeling of detected patterns for ML training
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import get_pending_patterns, update_pattern_validation, get_connection
from utils.logger import setup_logger
import sqlite3

logger = setup_logger("review_interface")

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    """Main review interface"""
    return render_template('review.html')

@app.route('/api/patterns/pending')
def get_pending():
    """Get pending patterns for review"""
    try:
        limit = request.args.get('limit', 100, type=int)
        patterns = get_pending_patterns(limit)
        
        return jsonify({
            'status': 'success',
            'count': len(patterns),
            'patterns': patterns
        })
    except Exception as e:
        logger.error(f"Error fetching pending patterns: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/patterns/<pattern_id>/validate', methods=['POST'])
def validate_pattern(pattern_id):
    """Validate a pattern with human input"""
    try:
        data = request.json
        
        validation_data = {
            'validation_status': 'VALID' if data.get('is_valid') else 'INVALID',
            'human_label': data.get('label'),
            'pattern_quality': data.get('quality', 3),
            'reviewed_at': 'CURRENT_TIMESTAMP'
        }
        
        success = update_pattern_validation(pattern_id, validation_data)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Pattern validated successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to update pattern'
            }), 500
    
    except Exception as e:
        logger.error(f"Error validating pattern: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/stats')
def get_stats():
    """Get review statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total patterns
        cursor.execute("SELECT COUNT(*) FROM patterns")
        total = cursor.fetchone()[0]
        
        # Pending
        cursor.execute("SELECT COUNT(*) FROM patterns WHERE validation_status = 'PENDING'")
        pending = cursor.fetchone()[0]
        
        # Valid
        cursor.execute("SELECT COUNT(*) FROM patterns WHERE validation_status = 'VALID'")
        valid = cursor.fetchone()[0]
        
        # Invalid
        cursor.execute("SELECT COUNT(*) FROM patterns WHERE validation_status = 'INVALID'")
        invalid = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total': total,
                'pending': pending,
                'valid': valid,
                'invalid': invalid,
                'progress_pct': ((valid + invalid) / total * 100) if total > 0 else 0
            }
        })
    
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    logger.info("Starting Pattern Review Interface...")
    logger.info("Access at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

