from django.contrib.auth.models import UserManager as BaseUserManager


class UserManager(BaseUserManager):
    """Кастомный менеджер пользователей."""

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})

    def active(self):
        return self.filter(is_active=True)

    def by_role(self, role):
        return self.active().filter(role=role)

    def admins(self):
        return self.by_role("admin")

    def accountants(self):
        return self.by_role("accountant")

    def managers(self):
        return self.by_role("manager")

    def procurement_managers(self):
        return self.by_role("procurement")
