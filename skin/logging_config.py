"""
Logging configuration for the skin disease detection application
Provides comprehensive logging for debugging, monitoring, and audit trails
"""

import logging
import logging.handlers
import os
from pathlib import Path

# Create logs directory
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'app.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'prediction_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'predictions.log'),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'errors.log'),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'security.log'),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'audit.log'),
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 20,
            'formatter': 'verbose',
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'debug.log'),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 3,
            'formatter': 'verbose',
            'filters': ['require_debug_true'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'skin': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'skin.views': {
            'handlers': ['console', 'file', 'prediction_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'skin.utils': {
            'handlers': ['console', 'file', 'debug_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'skin.services': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'skin.api': {
            'handlers': ['console', 'file', 'audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['audit_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}


def get_logger(name):
    """
    Convenience function to get a logger with the given name
    """
    return logging.getLogger(name)


def log_prediction_audit(user, image_name, prediction, confidence):
    """
    Log prediction events for audit trail
    """
    logger = get_logger('audit')
    logger.info(
        f"PREDICTION - User: {user.username}, Image: {image_name}, "
        f"Prediction: {prediction}, Confidence: {confidence:.2f}%"
    )


def log_security_event(event_type, user, details):
    """
    Log security-related events
    """
    logger = get_logger('django.security')
    logger.warning(
        f"SECURITY_EVENT - Type: {event_type}, User: {user.username if user else 'Anonymous'}, "
        f"Details: {details}"
    )


def log_api_call(endpoint, user, method, status_code):
    """
    Log API endpoint calls
    """
    logger = get_logger('skin.api')
    logger.info(
        f"API_CALL - Endpoint: {endpoint}, User: {user.username if user else 'Anonymous'}, "
        f"Method: {method}, Status: {status_code}"
    )
