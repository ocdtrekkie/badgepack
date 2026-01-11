from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json
import hashlib
from io import BytesIO
import requests
from urllib.parse import urljoin

# Initialize Flask app
instance_path = '/var'
app = Flask(__name__, template_folder='templates', instance_path=instance_path)
CORS(app)

# Database configuration
db_path = os.path.join(instance_path, 'badges.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 52428800  # 50MB max file size

db = SQLAlchemy(app)

# Database Model
class Badge(db.Model):
    __tablename__ = 'badges'
    
    id = db.Column(db.String(50), primary_key=True)
    version = db.Column(db.String(10))
    type = db.Column(db.String(100))
    badge_name = db.Column(db.String(255))
    description = db.Column(db.Text)
    issuer_name = db.Column(db.String(255))
    issuer_url = db.Column(db.String(500))
    issuer_email = db.Column(db.String(255))
    credential_provider = db.Column(db.String(100))
    issuance_date = db.Column(db.String(50))
    expires_date = db.Column(db.String(50))
    recipient_identity = db.Column(db.String(500))
    raw_data = db.Column(db.JSON)
    badge_image_data = db.Column(db.LargeBinary)
    image_hash = db.Column(db.String(64))
    image_mime_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_image=False):
        result = {
            'id': self.id,
            'version': self.version,
            'type': self.type,
            'badgeName': self.badge_name,
            'description': self.description,
            'issuerName': self.issuer_name,
            'issuerUrl': self.issuer_url,
            'issuerEmail': self.issuer_email,
            'credentialProvider': self.credential_provider,
            'issuanceDate': self.issuance_date,
            'expiresDate': self.expires_date,
            'recipientIdentity': self.recipient_identity,
            'rawData': self.raw_data,
            'hasImage': bool(self.badge_image_data),
            'imageMimeType': self.image_mime_type,
            'uploadedAt': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
        if include_image and self.badge_image_data:
            result['imageData'] = self.badge_image_data.hex()
        return result

# Create database tables
with app.app_context():
    db.create_all()

# ===== FRONTEND ROUTES =====

@app.route('/')
def serve_frontend():
    """Serve the main frontend HTML"""
    return render_template('index.html')

# ===== UTILITY ROUTES =====

@app.route('/api/fetch-remote', methods=['POST'])
def fetch_remote():
    """Proxy endpoint for fetching remote badge data with CORS support"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'Missing URL'}), 400
        
        # Validate URL
        if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'error': 'Invalid URL'}), 400
        
        # Fetch with timeout
        response = requests.get(url, timeout=5, headers={'Accept': 'application/json'})
        
        if response.status_code == 200:
            return jsonify({'data': response.json()}), 200
        else:
            return jsonify({'error': f'Remote server returned {response.status_code}'}), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 400
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON response'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== API ROUTES =====

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Backend is running'}), 200

@app.route('/api/badges', methods=['GET'])
def get_all_badges():
    """Get all badges (without images for performance)"""
    badges = Badge.query.all()
    return jsonify([badge.to_dict(include_image=False) for badge in badges]), 200

@app.route('/api/badges/<badge_id>', methods=['GET'])
def get_badge(badge_id):
    """Get single badge with full data"""
    badge = Badge.query.get(badge_id)
    if not badge:
        return jsonify({'error': 'Badge not found'}), 404
    return jsonify(badge.to_dict(include_image=True)), 200

@app.route('/api/badges/<badge_id>/image', methods=['GET'])
def get_badge_image(badge_id):
    """Get badge image directly"""
    badge = Badge.query.get(badge_id)
    if not badge or not badge.badge_image_data:
        return jsonify({'error': 'Badge or image not found'}), 404
    
    mime_type = badge.image_mime_type or 'image/png'
    return send_file(
        BytesIO(badge.badge_image_data),
        mimetype=mime_type,
        as_attachment=False
    )

@app.route('/api/badges', methods=['POST'])
def upload_badge():
    """Upload new badge with image"""
    try:
        # Parse badge data
        badge_data_str = request.form.get('badgeData')
        if not badge_data_str:
            return jsonify({'error': 'Missing badgeData'}), 400
        
        badge_data = json.loads(badge_data_str)
        
        # Get file if provided
        image_data = None
        image_mime_type = None
        image_hash = None
        
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                image_data = file.read()
                image_mime_type = file.content_type or 'image/png'
                
                # Calculate hash for deduplication
                image_hash = hashlib.sha256(image_data).hexdigest()
        
        # Create badge record
        badge = Badge(
            id=badge_data.get('id'),
            version=badge_data.get('version'),
            type=badge_data.get('type'),
            badge_name=badge_data.get('badgeName'),
            description=badge_data.get('description'),
            issuer_name=badge_data.get('issuerName'),
            issuer_url=badge_data.get('issuerUrl'),
            issuer_email=badge_data.get('issuerEmail'),
            credential_provider=badge_data.get('credentialProvider'),
            issuance_date=badge_data.get('issuanceDate'),
            expires_date=badge_data.get('expiresDate'),
            recipient_identity=badge_data.get('recipientIdentity'),
            raw_data=badge_data.get('rawData'),
            badge_image_data=image_data,
            image_hash=image_hash,
            image_mime_type=image_mime_type
        )
        
        db.session.add(badge)
        db.session.commit()
        
        return jsonify(badge.to_dict()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/badges/<badge_id>', methods=['PUT'])
def update_badge(badge_id):
    """Update badge metadata"""
    try:
        badge = Badge.query.get(badge_id)
        if not badge:
            return jsonify({'error': 'Badge not found'}), 404
        
        data = request.json
        
        # Update fields
        if 'badgeName' in data:
            badge.badge_name = data['badgeName']
        if 'description' in data:
            badge.description = data['description']
        if 'issuerName' in data:
            badge.issuer_name = data['issuerName']
        if 'issuerUrl' in data:
            badge.issuer_url = data['issuerUrl']
        if 'credentialProvider' in data:
            badge.credential_provider = data['credentialProvider']
        
        db.session.commit()
        return jsonify(badge.to_dict()), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/badges/<badge_id>', methods=['DELETE'])
def delete_badge(badge_id):
    """Delete a badge and its image"""
    try:
        badge = Badge.query.get(badge_id)
        if not badge:
            return jsonify({'error': 'Badge not found'}), 404
        
        db.session.delete(badge)
        db.session.commit()
        
        return jsonify({'message': 'Badge deleted successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/badges/search', methods=['POST'])
def search_badges():
    """Search badges by criteria"""
    try:
        criteria = request.json or {}
        
        query = Badge.query
        
        # Filter by issuer
        if criteria.get('issuer'):
            query = query.filter(
                db.or_(
                    Badge.issuer_name == criteria['issuer'],
                    Badge.issuer_url == criteria['issuer']
                )
            )
        
        # Filter by provider
        if criteria.get('provider'):
            query = query.filter(Badge.credential_provider == criteria['provider'])
        
        # Search in name and description
        if criteria.get('search'):
            search_term = f"%{criteria['search']}%"
            query = query.filter(
                db.or_(
                    Badge.badge_name.ilike(search_term),
                    Badge.description.ilike(search_term),
                    Badge.issuer_name.ilike(search_term)
                )
            )
        
        badges = query.all()
        return jsonify([badge.to_dict(include_image=False) for badge in badges]), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get badge statistics"""
    try:
        total = Badge.query.count()
        
        # Count unique issuers
        issuers = db.session.query(db.distinct(Badge.issuer_name)).filter(
            Badge.issuer_name.isnot(None)
        ).count()
        issuer_urls = db.session.query(db.distinct(Badge.issuer_url)).filter(
            Badge.issuer_url.isnot(None)
        ).count()
        unique_issuers = issuers + issuer_urls
        
        # Count unique providers
        unique_providers = db.session.query(db.distinct(Badge.credential_provider)).filter(
            Badge.credential_provider.isnot(None)
        ).count()
        
        # Count badges with images
        badges_with_images = Badge.query.filter(Badge.badge_image_data.isnot(None)).count()
        
        return jsonify({
            'totalBadges': total,
            'uniqueIssuers': unique_issuers,
            'uniqueProviders': unique_providers,
            'badgesWithImages': badges_with_images
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/export', methods=['GET'])
def export_badges():
    """Export all badges as JSON"""
    try:
        badges = Badge.query.all()
        badges_list = [badge.to_dict(include_image=True) for badge in badges]
        
        return jsonify({
            'exportDate': datetime.utcnow().isoformat(),
            'totalBadges': len(badges_list),
            'badges': badges_list
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
