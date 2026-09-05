"""
Advanced services for batch processing, export, and analysis
"""

import io
import logging
import json
from datetime import datetime
from csv import DictWriter
from .models import PredictionHistory
from .utils import ModelCache, ImageProcessor, PredictionUtils

logger = logging.getLogger(__name__)


class BatchPredictionService:
    """
    Handle batch predictions for multiple images
    """

    @staticmethod
    def process_batch(image_paths, class_names):
        """
        Process multiple images in batch for efficiency
        """
        try:
            model = ModelCache.get_model()
            logger.info(f"Starting batch processing of {len(image_paths)} images")

            results = []
            for idx, image_path in enumerate(image_paths):
                try:
                    image_array = ImageProcessor.process_image(image_path)
                    prediction = model.predict(image_array, verbose=0)

                    predicted_idx = int(np.argmax(prediction[0]))
                    confidence = float(np.max(prediction[0]) * 100)
                    predicted_class = class_names[predicted_idx] if predicted_idx < len(class_names) else f"Class {predicted_idx}"

                    class_scores = PredictionUtils.format_class_scores(prediction, class_names)

                    results.append({
                        'image_path': image_path,
                        'prediction': predicted_class,
                        'confidence': round(confidence, 2),
                        'class_scores': class_scores,
                        'timestamp': datetime.now().isoformat()
                    })

                    logger.info(f"Batch [{idx+1}/{len(image_paths)}] - {predicted_class} ({confidence:.2f}%)")

                except Exception as e:
                    logger.error(f"Error processing image {image_path}: {str(e)}")
                    results.append({
                        'image_path': image_path,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })

            logger.info(f"Batch processing completed. {len([r for r in results if 'error' not in r])} successful predictions")
            return results

        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            raise


class ExportService:
    """
    Export prediction data in various formats
    """

    @staticmethod
    def export_to_csv(predictions, filename=None):
        """
        Export predictions to CSV format
        """
        try:
            if filename is None:
                filename = f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            output = io.StringIO()
            fieldnames = ['image', 'prediction', 'confidence', 'date', 'disease_description']

            writer = DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            disease_descriptions = {
                "Acne": "Common skin condition caused by clogged pores",
                "Dermatitis": "Skin irritation or inflammation",
                "Eczema": "Chronic inflammatory skin condition",
                "Melanoma": "Serious form of skin cancer",
                "Psoriasis": "Autoimmune condition with scaly patches",
                "Ringworm": "Fungal infection causing circular patches",
                "Vitiligo": "Loss of skin pigment creating pale patches"
            }

            for pred in predictions:
                writer.writerow({
                    'image': str(pred.image).split('/')[-1],
                    'prediction': pred.prediction,
                    'confidence': f"{pred.confidence:.2f}%",
                    'date': pred.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'disease_description': disease_descriptions.get(pred.prediction, "N/A")
                })

            logger.info(f"Exported {len(predictions)} predictions to CSV: {filename}")
            return output.getvalue(), filename

        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}")
            raise

    @staticmethod
    def export_to_json(predictions, filename=None):
        """
        Export predictions to JSON format with full details
        """
        try:
            if filename is None:
                filename = f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            data = {
                'export_date': datetime.now().isoformat(),
                'total_predictions': len(predictions),
                'predictions': [
                    {
                        'image': str(pred.image),
                        'prediction': pred.prediction,
                        'confidence': pred.confidence,
                        'created_at': pred.created_at.isoformat()
                    }
                    for pred in predictions
                ]
            }

            json_str = json.dumps(data, indent=2)
            logger.info(f"Exported {len(predictions)} predictions to JSON: {filename}")
            return json_str, filename

        except Exception as e:
            logger.error(f"JSON export failed: {str(e)}")
            raise

    @staticmethod
    def export_to_pdf(predictions, user=None):
        """
        Export predictions to PDF report format
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors

            filename = f"prediction_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#0f766e'),
                spaceAfter=30,
                alignment=1
            )
            elements.append(Paragraph("Skin Disease Detection Report", title_style))
            elements.append(Spacer(1, 0.2*inch))

            # Metadata
            meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            if user:
                meta_text += f"<br/>User: {user.get_full_name() or user.username}"
            elements.append(Paragraph(meta_text, styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))

            # Table data
            table_data = [['Image', 'Prediction', 'Confidence', 'Date']]
            for pred in predictions:
                table_data.append([
                    str(pred.image).split('/')[-1][:20],
                    pred.prediction,
                    f"{pred.confidence:.2f}%",
                    pred.created_at.strftime('%Y-%m-%d')
                ])

            # Create table
            table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(table)
            doc.build(elements)

            logger.info(f"Exported {len(predictions)} predictions to PDF: {filename}")
            return buffer.getvalue(), filename

        except ImportError:
            logger.warning("reportlab not installed. PDF export requires: pip install reportlab")
            raise ImportError("PDF export requires reportlab package")
        except Exception as e:
            logger.error(f"PDF export failed: {str(e)}")
            raise


class ComparisonService:
    """
    Compare predictions across multiple images or time periods
    """

    @staticmethod
    def compare_predictions(prediction_ids):
        """
        Compare multiple predictions side-by-side
        """
        try:
            predictions = PredictionHistory.objects.filter(id__in=prediction_ids)

            comparison_data = {
                'predictions': [],
                'statistics': {
                    'average_confidence': 0,
                    'highest_confidence': 0,
                    'lowest_confidence': 100,
                    'disease_distribution': {}
                }
            }

            total_confidence = 0
            disease_counts = {}

            for pred in predictions:
                comparison_data['predictions'].append({
                    'id': pred.id,
                    'image': str(pred.image),
                    'prediction': pred.prediction,
                    'confidence': pred.confidence,
                    'date': pred.created_at.isoformat()
                })

                total_confidence += pred.confidence
                comparison_data['statistics']['highest_confidence'] = max(
                    comparison_data['statistics']['highest_confidence'],
                    pred.confidence
                )
                comparison_data['statistics']['lowest_confidence'] = min(
                    comparison_data['statistics']['lowest_confidence'],
                    pred.confidence
                )

                disease_counts[pred.prediction] = disease_counts.get(pred.prediction, 0) + 1

            if predictions.count() > 0:
                comparison_data['statistics']['average_confidence'] = round(
                    total_confidence / predictions.count(), 2
                )

            comparison_data['statistics']['disease_distribution'] = disease_counts

            logger.info(f"Comparison generated for {predictions.count()} predictions")
            return comparison_data

        except Exception as e:
            logger.error(f"Comparison failed: {str(e)}")
            raise

    @staticmethod
    def get_prediction_trends(user, days=30):
        """
        Analyze prediction trends over time
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count

            start_date = timezone.now() - timedelta(days=days)
            predictions = PredictionHistory.objects.filter(
                user=user,
                created_at__gte=start_date
            ).values('prediction').annotate(count=Count('id'))

            trends = {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'total_predictions': sum(p['count'] for p in predictions),
                'disease_frequency': {p['prediction']: p['count'] for p in predictions}
            }

            logger.info(f"Trends generated for user {user.username} ({days} days)")
            return trends

        except Exception as e:
            logger.error(f"Trend analysis failed: {str(e)}")
            raise


# Import numpy for batch processing
import numpy as np
