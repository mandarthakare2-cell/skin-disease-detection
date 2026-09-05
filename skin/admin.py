from django.contrib import admin
from django.utils.html import format_html
from .models import PredictionHistory, LoginTracker


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    """Admin interface for prediction history"""
    
    list_display = ('user', 'prediction', 'confidence_display', 'created_at', 'image_thumbnail')
    list_filter = ('prediction', 'created_at', 'confidence')
    search_fields = ('user__username', 'prediction')
    readonly_fields = ('created_at', 'image_preview')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User & Prediction', {
            'fields': ('user', 'prediction', 'confidence')
        }),
        ('Image', {
            'fields': ('image', 'image_preview')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def confidence_display(self, obj):
        """Display confidence as percentage with color coding"""
        if obj.confidence >= 80:
            color = '#28a745'  # Green
        elif obj.confidence >= 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color,
            obj.confidence
        )
    confidence_display.short_description = 'Confidence'
    
    def image_thumbnail(self, obj):
        """Display image thumbnail in list"""
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.image.url
            )
        return '-'
    image_thumbnail.short_description = 'Image'
    
    def image_preview(self, obj):
        """Display full image preview in detail view"""
        if obj.image:
            return format_html(
                '<img src="{}" width="300" height="300" style="object-fit: contain; border-radius: 5px;" />',
                obj.image.url
            )
        return 'No image'
    image_preview.short_description = 'Image Preview'


@admin.register(LoginTracker)
class LoginTrackerAdmin(admin.ModelAdmin):
    """Admin interface for login tracking"""
    
    list_display = ('user', 'login_time', 'ip_address')
    list_filter = ('login_time', 'user')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('login_time',)
    ordering = ('-login_time',)
    
    fieldsets = (
        ('Login Information', {
            'fields': ('user', 'login_time')
        }),
        ('Network', {
            'fields': ('ip_address',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual addition of login records"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Require superuser permission to delete"""
        return request.user.is_superuser


# Customize admin site
admin.site.site_header = "Skin Disease Detection Admin"
admin.site.site_title = "Admin Portal"
admin.site.index_title = "Welcome to Skin Disease Detection Admin"
