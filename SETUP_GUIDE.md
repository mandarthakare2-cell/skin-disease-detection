# Quick Setup Guide - Advanced Features

## 🚀 Installation & Setup (5 minutes)

### Step 1: Install New Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `djangorestframework` - REST API
- `django-redis` - Caching (optional, uses in-memory by default)
- `reportlab` - PDF export
- `python-json-logger` - JSON logging
- `python-dotenv` - Environment variables

### Step 2: Create Logs Directory
```bash
mkdir logs
```

### Step 3: Run Database Migrations
```bash
python manage.py migrate
```

### Step 4: Run Tests (Optional but Recommended)
```bash
python manage.py test skin.tests -v 2
```

### Step 5: Start Server
```bash
python manage.py runserver
```

Server will be available at: **http://127.0.0.1:8000/**

---

## 📋 What's New?

### New Files Created:
1. **`skin/utils.py`** - Performance optimization utilities
   - `ModelCache` - Singleton model caching
   - `ImageProcessor` - Image processing with caching
   - `PredictionUtils` - Prediction analysis
   - `QueryOptimizer` - Database optimization

2. **`skin/services.py`** - Advanced services
   - `BatchPredictionService` - Batch image processing
   - `ExportService` - CSV/JSON/PDF export
   - `ComparisonService` - Prediction comparison & trends

3. **`skin/api.py`** - REST API endpoints
   - 7 new API endpoints for mobile/external apps
   - Full authentication and rate limiting

4. **`skin/logging_config.py`** - Comprehensive logging
   - 6 separate log files for different concerns
   - Rotating file handlers

5. **`ADVANCED_FEATURES.md`** - Complete documentation
   - Feature descriptions
   - API documentation
   - Performance metrics
   - Deployment guide

### Updated Files:
1. **`skin/views.py`** - Integrated new utilities
   - Uses `ModelCache` instead of global variable
   - Better error logging

2. **`skin/admin.py`** - Enhanced Django admin
   - Prediction management interface
   - Login tracking interface
   - Image previews and confidence display

3. **`skin/tests.py`** - Comprehensive test suite
   - 8 test classes
   - 20+ test methods
   - Full coverage

4. **`config/settings.py`** - New configurations
   - Cache settings
   - REST Framework config
   - Logging setup
   - Security settings
   - File upload limits

5. **`config/urls.py`** - New URL routes
   - 7 API endpoints registered

6. **`requirements.txt`** - New dependencies

---

## 🎯 Quick Start Examples

### Example 1: Use the API (Python)
```python
import requests

# Login first to get session
session = requests.Session()
session.post('http://127.0.0.1:8000/login/', data={
    'username': 'testuser',
    'password': 'testpass'
})

# Make prediction
with open('skin_image.jpg', 'rb') as f:
    response = session.post(
        'http://127.0.0.1:8000/api/predict/',
        files={'image': f}
    )
    print(response.json())

# Output:
# {
#     "success": true,
#     "prediction": "Melanoma",
#     "confidence": 92.5,
#     "class_scores": [...],
#     "warning": false
# }
```

### Example 2: Export Predictions
```python
# Get CSV export
response = session.get('http://127.0.0.1:8000/api/export/?format=csv&limit=50')
with open('predictions.csv', 'wb') as f:
    f.write(response.content)
```

### Example 3: Compare Predictions
```python
# Compare prediction IDs 1, 2, 3
response = session.get('http://127.0.0.1:8000/api/compare/?ids=1,2,3')
print(response.json())

# Output:
# {
#     "predictions": [...],
#     "statistics": {
#         "average_confidence": 78.75,
#         "highest_confidence": 92.0,
#         "disease_distribution": {"Acne": 2, "Melanoma": 1}
#     }
# }
```

---

## 📊 Accessing Admin Interface

### Django Admin Features:

1. **Prediction Management**
   ```
   URL: http://127.0.0.1:8000/admin/
   - View all predictions
   - Filter by disease, date, confidence
   - See image thumbnails
   - Color-coded confidence display
   ```

2. **Login Tracking**
   ```
   - Monitor user login patterns
   - Track IP addresses
   - View login timestamps
   ```

**Create superuser:**
```bash
python manage.py createsuperuser
# Follow prompts to create admin account
```

---

## 🔍 Monitoring & Logging

### View Logs:
```bash
# Application logs
tail -f logs/app.log

# Prediction-specific logs
tail -f logs/predictions.log

# Error logs
tail -f logs/errors.log

# Security events
tail -f logs/security.log

# Audit trail
tail -f logs/audit.log
```

### Log Format:
```
ERROR 2026-09-01 12:00:00 views 12345 67890 Error analyzing image: Model file not found
INFO 2026-09-01 12:00:01 utils 12345 67890 Image array cached: image_abc123
WARNING 2026-09-01 12:00:02 api 12345 67890 SECURITY_EVENT - Type: login_failed
```

---

## ⚡ Performance Tips

### 1. Enable Caching
The app uses Django's in-memory cache by default. For better performance:

**Install Redis:**
```bash
# Windows (if using WSL)
sudo apt-get install redis-server
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:latest
```

**Update settings.py:**
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

### 2. Use Batch Predictions
Instead of single predictions, batch multiple images:
```python
# Faster (single request for 50 images)
POST /api/batch-predict/

# Slower (50 requests for 50 images)
POST /api/predict/  # repeated 50 times
```

### 3. Monitor Performance
```bash
# Check Django ORM queries
# Add to settings.py in development:
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['console'],
    'level': 'DEBUG',
}
```

---

## 🧪 Running Tests

### All Tests:
```bash
python manage.py test skin.tests
```

### Specific Test Class:
```bash
python manage.py test skin.tests.ImageProcessorTestCase
```

### With Coverage:
```bash
pip install coverage

coverage run --source='skin' manage.py test
coverage report
coverage html  # Open htmlcov/index.html
```

### Test Results Expected:
```
Ran 20 tests in 0.234s

OK - All tests passed!
```

---

## 🚨 Troubleshooting

### Issue: "No module named 'rest_framework'"
```bash
pip install djangorestframework
```

### Issue: "Model file not found"
```
- Ensure skin_disease_model.h5 exists in skin/model/ directory
- Check file path in logs: logs/errors.log
```

### Issue: "AttributeError: 'QuerySet' has no attribute 'extra'"
```
- Upgrade Django version
- Or use ORM methods instead of .extra()
```

### Issue: Cache not working
```bash
# Clear cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

---

## 📈 Next Steps

### Short Term:
- [ ] Test all API endpoints
- [ ] Verify logging is working
- [ ] Run unit tests
- [ ] Test batch predictions

### Medium Term:
- [ ] Deploy to staging environment
- [ ] Set up Redis for caching
- [ ] Configure production settings
- [ ] Load test the API

### Long Term:
- [ ] Add model versioning
- [ ] Implement automated retraining
- [ ] Set up monitoring/alerts
- [ ] Create mobile app using API

---

## 📚 Documentation

- **Full Guide:** `ADVANCED_FEATURES.md`
- **API Docs:** `ADVANCED_FEATURES.md` → "API Documentation"
- **Code:** See docstrings in files

## 🤝 Support

Run tests if something breaks:
```bash
python manage.py test skin.tests --debug-mode
```

Check logs:
```bash
tail -f logs/*.log
```

---

**Ready to go!** 🚀

Start your server with: `python manage.py runserver`

Visit: http://127.0.0.1:8000/
