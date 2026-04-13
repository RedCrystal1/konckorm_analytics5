from django.http import JsonResponse
from django.utils import timezone


class APITokenAuthMiddleware:
    """Аутентификация API-запросов по токену.

    Проверяет заголовок Authorization: Token <key>
    для всех запросов к /api/v1/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/v1/"):
            # Пропускаем документацию API
            if request.path == "/api/v1/" or request.path == "/api/v1/docs/":
                return self.get_response(request)

            auth_header = request.META.get("HTTP_AUTHORIZATION", "")

            if not auth_header.startswith("Token "):
                return JsonResponse(
                    {"error": "Требуется заголовок Authorization: Token <key>"},
                    status=401,
                )

            token_key = auth_header[6:].strip()

            from .models import APIToken

            try:
                token = APIToken.objects.get(key=token_key, is_active=True)
            except APIToken.DoesNotExist:
                return JsonResponse(
                    {"error": "Недействительный или отключённый токен"},
                    status=403,
                )

            # Обновляем время последнего использования
            token.last_used_at = timezone.now()
            token.save(update_fields=["last_used_at"])

            # Сохраняем токен в request для использования во views
            request.api_token = token

        return self.get_response(request)
