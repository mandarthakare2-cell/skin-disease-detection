"""
REST API endpoints for the skin disease detection system
Provides JSON-based API for mobile apps and external integrations
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import PredictionHistory
from .utils import ModelCache, ImageProcessor, PredictionUtils, log_prediction
from .services import (
    BatchPredictionService,
    ExportService,
    ComparisonService
)
import numpy as np

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_image(request):
    """
    API endpoint for single image prediction
    POST /api/predict/
    """
    try:
        if 'image' not in request.FILES:
            return Response(
                {'error': 'No image provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_image = request.FILES['image']

        # Validate file type
        valid_types = ['image/jpeg', 'image/png', 'image/webp']
        if uploaded_image.content_type not in valid_types:
            return Response(
                {'error': 'Invalid image format. Allowed: JPEG, PNG, WebP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size (5MB max)
        if uploaded_image.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Image too large. Maximum size: 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save image temporarily
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            for chunk in uploaded_image.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            # Load model and process image
            model = ModelCache.get_model()
            image_array = ImageProcessor.process_image(tmp_path)

            # Make prediction
            prediction_result = model.predict(image_array, verbose=0)
            predicted_idx = int(np.argmax(prediction_result[0]))
            confidence = float(np.max(prediction_result[0]) * 100)

            # Get class names
            from .views import get_class_names
            class_names = get_class_names()
            predicted_class = class_names[predicted_idx] if predicted_idx < len(class_names) else f"Class {predicted_idx}"

            # Format class scores
            class_scores = PredictionUtils.format_class_scores(prediction_result, class_names)

            # Analyze confidence
            confidence_analysis = PredictionUtils.analyze_confidence(confidence)

            # Save to database
            from .views import get_client_ip
            history = PredictionHistory.objects.create(
                user=request.user,
                image=uploaded_image,
                prediction=predicted_class,
                confidence=round(confidence, 2)
            )

            # Log prediction
            log_prediction(request.user, uploaded_image.name, predicted_class, confidence)

            return Response({
                'success': True,
                'prediction': predicted_class,
                'confidence': round(confidence, 2),
                'class_scores': class_scores,
                'confidence_level': confidence_analysis['status'],
                'warning': confidence_analysis['warning'],
                'warning_message': confidence_analysis['message'],
                'history_id': history.id,
                'timestamp': history.created_at.isoformat()
            }, status=status.HTTP_200_OK)

        finally:
            # Clean up temporary file
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Prediction API error: {str(e)}")
        return Response(
            {'error': f'Prediction failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_predict(request):
    """
    API endpoint for batch image prediction
    POST /api/batch-predict/
    """
    try:
        if 'images' not in request.FILES:
            return Response(
                {'error': 'No images provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        images = request.FILES.getlist('images')
        if len(images) == 0:
            return Response(
                {'error': 'No images provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(images) > 50:
            return Response(
                {'error': 'Maximum 50 images per batch'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Batch prediction initiated for user {request.user.username} with {len(images)} images")

        results = {
            'total_images': len(images),
            'successful': 0,
            'failed': 0,
            'predictions': []
        }

        # Save images temporarily and process
        import tempfile
        import os
        from .views import get_class_names

        class_names = get_class_names()
        model = ModelCache.get_model()

        for idx, image_file in enumerate(images):
            try:
                # Validate
                if image_file.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
                    results['predictions'].append({
                        'file': image_file.name,
                        'error': 'Invalid format'
                    })
                    results['failed'] += 1
                    continue

                # Save temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    for chunk in image_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                try:
                    # Process
                    image_array = ImageProcessor.process_image(tmp_path)
                    prediction_result = model.predict(image_array, verbose=0)

                    predicted_idx = int(np.argmax(prediction_result[0]))
                    confidence = float(np.max(prediction_result[0]) * 100)
                    predicted_class = class_names[predicted_idx] if predicted_idx < len(class_names) else f"Class {predicted_idx}"

                    # Save to database
                    PredictionHistory.objects.create(
                        user=request.user,
                        image=image_file,
                        prediction=predicted_class,
                        confidence=round(confidence, 2)
                    )

                    results['predictions'].append({
                        'file': image_file.name,
                        'prediction': predicted_class,
                        'confidence': round(confidence, 2)
                    })
                    results['successful'] += 1

                finally:
                    os.unlink(tmp_path)

            except Exception as e:
                logger.error(f"Batch image error ({image_file.name}): {str(e)}")
                results['predictions'].append({
                    'file': image_file.name,
                    'error': str(e)
                })
                results['failed'] += 1

        return Response(results, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Batch prediction API error: {str(e)}")
        return Response(
            {'error': f'Batch prediction failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prediction_history(request):
    """
    API endpoint to get user's prediction history
    GET /api/history/?limit=20&offset=0
    """
    try:
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))

        if limit > 100:
            limit = 100

        from .utils import QueryOptimizer
        predictions = QueryOptimizer.get_user_prediction_history(request.user, limit, offset)
        total_count = PredictionHistory.objects.filter(user=request.user).count()

        history_data = [
            {
                'id': p.id,
                'image': str(p.image),
                'prediction': p.prediction,
                'confidence': p.confidence,
                'created_at': p.created_at.isoformat()
            }
            for p in predictions
        ]

        return Response({
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'count': len(history_data),
            'predictions': history_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"History API error: {str(e)}")
        return Response(
            {'error': f'Failed to fetch history: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_predictions(request):
    """
    API endpoint to export predictions
    GET /api/export/?format=csv&limit=50
    """
    try:
        format_type = request.GET.get('format', 'csv').lower()
        limit = int(request.GET.get('limit', 50))

        if limit > 1000:
            limit = 1000

        predictions = PredictionHistory.objects.filter(
            user=request.user
        ).order_by('-created_at')[:limit]

        if format_type == 'csv':
            content, filename = ExportService.export_to_csv(predictions)
            from django.http import HttpResponse
            response = HttpResponse(content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif format_type == 'json':
            content, filename = ExportService.export_to_json(predictions)
            return Response({
                'filename': filename,
                'data': eval(content)  # Safe since we generated it
            }, status=status.HTTP_200_OK)

        elif format_type == 'pdf':
            try:
                content, filename = ExportService.export_to_pdf(predictions, request.user)
                from django.http import HttpResponse
                response = HttpResponse(content, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            except ImportError:
                return Response(
                    {'error': 'PDF export requires reportlab. Install with: pip install reportlab'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            return Response(
                {'error': 'Invalid format. Supported: csv, json, pdf'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except Exception as e:
        logger.error(f"Export API error: {str(e)}")
        return Response(
            {'error': f'Export failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comparison(request):
    """
    API endpoint to compare multiple predictions
    GET /api/compare/?ids=1,2,3,4
    """
    try:
        ids_param = request.GET.get('ids', '')
        if not ids_param:
            return Response(
                {'error': 'Please provide prediction IDs (ids=1,2,3)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ids = [int(x.strip()) for x in ids_param.split(',')]
        if len(ids) < 2:
            return Response(
                {'error': 'Provide at least 2 prediction IDs to compare'},
                status=status.HTTP_400_BAD_REQUEST
            )

        comparison_data = ComparisonService.compare_predictions(ids)
        return Response(comparison_data, status=status.HTTP_200_OK)

    except ValueError:
        return Response(
            {'error': 'Invalid ID format'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Comparison API error: {str(e)}")
        return Response(
            {'error': f'Comparison failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics(request):
    """
    API endpoint for user analytics
    GET /api/analytics/?days=30
    """
    try:
        days = int(request.GET.get('days', 30))
        if days < 1 or days > 365:
            days = 30

        from .services import ComparisonService
        trends = ComparisonService.get_prediction_trends(request.user, days)

        return Response(trends, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Analytics API error: {str(e)}")
        return Response(
            {'error': f'Analytics failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def api_status(request):
    """
    API status endpoint - no authentication required
    GET /api/status/
    """
    return Response({
        'status': 'operational',
        'version': '2.0',
        'endpoints': {
            'predict': 'POST /api/predict/',
            'batch_predict': 'POST /api/batch-predict/',
            'history': 'GET /api/history/',
            'export': 'GET /api/export/',
            'compare': 'GET /api/compare/',
            'analytics': 'GET /api/analytics/'
        }
    })
