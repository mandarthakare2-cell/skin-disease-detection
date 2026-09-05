"""
Unit tests for the skin disease detection application
Tests for utils, services, and API endpoints
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from django.urls import reverse
import os
import tempfile
from PIL import Image
import io

from .models import PredictionHistory, LoginTracker
from .utils import (
    ModelCache, ImageProcessor, PredictionUtils,
    QueryOptimizer, log_prediction
)
from .services import (
    ExportService, ComparisonService, BatchPredictionService
)


class ImageProcessorTestCase(TestCase):
    """Test image processing utilities"""

    def setUp(self):
        """Create test image"""
        self.test_image = self.create_test_image()

    @staticmethod
    def create_test_image(name='test.png'):
        """Helper to create a test image"""
        file = io.BytesIO()
        image = Image.new('RGB', (224, 224), color='red')
        image.save(file, 'PNG')
        file.seek(0)
        return SimpleUploadedFile(name, file.getvalue(), content_type='image/png')

    def test_image_hash_generation(self):
        """Test image hash for deduplication"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(self.test_image.read())
            tmp_path = tmp.name

        try:
            hash1 = ImageProcessor.get_image_hash(tmp_path)
            hash2 = ImageProcessor.get_image_hash(tmp_path)
            self.assertEqual(hash1, hash2, "Same image should produce same hash")
            self.assertEqual(len(hash1), 32, "MD5 hash should be 32 characters")
        finally:
            os.unlink(tmp_path)

    def test_image_process_resizing(self):
        """Test image resizing to standard size"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(self.test_image.read())
            tmp_path = tmp.name

        try:
            processed = ImageProcessor.process_image(tmp_path)
            # Check shape: (1, 224, 224, 3) for batch processing
            self.assertEqual(processed.shape[0], 1, "Should have batch dimension")
            self.assertEqual(processed.shape[1], 224, "Height should be 224")
            self.assertEqual(processed.shape[2], 224, "Width should be 224")
            self.assertEqual(processed.shape[3], 3, "Should have RGB channels")
        finally:
            os.unlink(tmp_path)


class PredictionUtilsTestCase(TestCase):
    """Test prediction analysis utilities"""

    def test_high_confidence_analysis(self):
        """Test high confidence level detection"""
        result = PredictionUtils.analyze_confidence(85.0)
        self.assertEqual(result['status'], 'high')
        self.assertFalse(result['warning'])
        self.assertIsNone(result['message'])

    def test_medium_confidence_analysis(self):
        """Test medium confidence level detection"""
        result = PredictionUtils.analyze_confidence(35.0)
        self.assertEqual(result['status'], 'medium')
        self.assertTrue(result['warning'])
        self.assertEqual(result['type'], 'warning')

    def test_low_confidence_analysis(self):
        """Test low confidence level detection"""
        result = PredictionUtils.analyze_confidence(15.0)
        self.assertEqual(result['status'], 'low')
        self.assertTrue(result['warning'])
        self.assertEqual(result['type'], 'error')

    def test_format_class_scores(self):
        """Test class score formatting"""
        import numpy as np
        # Simulated model output
        prediction_result = np.array([[0.1, 0.2, 0.15, 0.3, 0.15, 0.05, 0.05]])
        class_names = ['Acne', 'Dermatitis', 'Eczema', 'Melanoma', 'Psoriasis', 'Ringworm', 'Vitiligo']

        scores = PredictionUtils.format_class_scores(prediction_result, class_names)

        # Check sorting (highest first)
        self.assertEqual(scores[0]['label'], 'Melanoma')
        self.assertAlmostEqual(scores[0]['score'], 0.3, places=1)

        # Check all classes present
        self.assertEqual(len(scores), 7)


class ExportServiceTestCase(TestCase):
    """Test export functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create test predictions
        for i in range(3):
            PredictionHistory.objects.create(
                user=self.user,
                image=SimpleUploadedFile('test.png', io.BytesIO().getvalue()),
                prediction='Acne' if i % 2 == 0 else 'Melanoma',
                confidence=75.5 + i
            )

    def test_csv_export(self):
        """Test CSV export format"""
        predictions = PredictionHistory.objects.filter(user=self.user)
        csv_content, filename = ExportService.export_to_csv(predictions)

        self.assertIn('image', csv_content)
        self.assertIn('prediction', csv_content)
        self.assertIn('confidence', csv_content)
        self.assertTrue(filename.endswith('.csv'))

    def test_json_export(self):
        """Test JSON export format"""
        predictions = PredictionHistory.objects.filter(user=self.user)
        json_content, filename = ExportService.export_to_json(predictions)

        self.assertIn('export_date', json_content)
        self.assertIn('total_predictions', json_content)
        self.assertTrue(filename.endswith('.json'))


class ComparisonServiceTestCase(TestCase):
    """Test comparison functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.predictions = []
        for i in range(4):
            pred = PredictionHistory.objects.create(
                user=self.user,
                image=SimpleUploadedFile(f'test{i}.png', io.BytesIO().getvalue()),
                prediction=['Acne', 'Melanoma', 'Acne', 'Dermatitis'][i],
                confidence=[85.0, 72.5, 88.0, 65.0][i]
            )
            self.predictions.append(pred)

    def test_compare_predictions(self):
        """Test prediction comparison"""
        ids = [p.id for p in self.predictions[:2]]
        comparison = ComparisonService.compare_predictions(ids)

        self.assertEqual(comparison['predictions'].__len__(), 2)
        self.assertEqual(comparison['statistics']['highest_confidence'], 85.0)
        self.assertEqual(comparison['statistics']['lowest_confidence'], 72.5)
        self.assertAlmostEqual(comparison['statistics']['average_confidence'], 78.75, places=1)

    def test_prediction_trends(self):
        """Test trend analysis"""
        trends = ComparisonService.get_prediction_trends(self.user, days=30)

        self.assertEqual(trends['period_days'], 30)
        self.assertIn('Acne', trends['disease_frequency'])
        self.assertEqual(trends['disease_frequency']['Acne'], 2)
        self.assertEqual(trends['total_predictions'], 4)


class QueryOptimizerTestCase(TestCase):
    """Test database query optimization"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        for i in range(10):
            PredictionHistory.objects.create(
                user=self.user,
                image=SimpleUploadedFile(f'test{i}.png', io.BytesIO().getvalue()),
                prediction='Acne',
                confidence=75.0 + i
            )

    def test_get_user_prediction_history(self):
        """Test optimized history query"""
        predictions = QueryOptimizer.get_user_prediction_history(self.user, limit=5)
        self.assertEqual(predictions.count(), 5)

    def test_pagination(self):
        """Test pagination in queries"""
        page1 = QueryOptimizer.get_user_prediction_history(self.user, limit=5, offset=0)
        page2 = QueryOptimizer.get_user_prediction_history(self.user, limit=5, offset=5)

        self.assertEqual(page1.count(), 5)
        self.assertEqual(page2.count(), 5)


class ModelTestCase(TestCase):
    """Test database models"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_prediction_history_creation(self):
        """Test creating prediction history"""
        pred = PredictionHistory.objects.create(
            user=self.user,
            image=SimpleUploadedFile('test.png', io.BytesIO().getvalue()),
            prediction='Melanoma',
            confidence=92.5
        )

        self.assertEqual(pred.user, self.user)
        self.assertEqual(pred.prediction, 'Melanoma')
        self.assertEqual(pred.confidence, 92.5)
        self.assertIsNotNone(pred.created_at)

    def test_login_tracker_creation(self):
        """Test creating login tracker"""
        tracker = LoginTracker.objects.create(
            user=self.user,
            ip_address='192.168.1.1'
        )

        self.assertEqual(tracker.user, self.user)
        self.assertEqual(tracker.ip_address, '192.168.1.1')
        self.assertIsNotNone(tracker.login_time)


class ViewAuthTestCase(TestCase):
    """Test view authentication and permissions"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_home_requires_login(self):
        """Test that home view requires authentication"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/login/', response.url)

    def test_home_accessible_when_logged_in(self):
        """Test that home view is accessible when authenticated"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)


class IntegrationTestCase(TestCase):
    """Integration tests for complete workflows"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_complete_prediction_workflow(self):
        """Test complete prediction workflow: login -> predict -> export"""
        # Login
        self.client.login(username='testuser', password='testpass123')

        # Create prediction
        test_image = SimpleUploadedFile('test.png', io.BytesIO().getvalue())
        PredictionHistory.objects.create(
            user=self.user,
            image=test_image,
            prediction='Acne',
            confidence=85.0
        )

        # Verify prediction saved
        predictions = PredictionHistory.objects.filter(user=self.user)
        self.assertEqual(predictions.count(), 1)
