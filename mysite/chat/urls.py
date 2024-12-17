from django.urls import path, include
from . import views
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = routers.DefaultRouter()

# router.register('test', views.test, 'test')
router.register('rooms', views.RoomViewSet, 'rooms')
# router.register('main', views.index, 'main')
router.register('register', views.RegisterView, 'reg')


urlpatterns = [
    path('/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    # path('test/', views.test),
    # path('index/', views.index, name='index'),
    # path('token/', views.RegisterView.as_view(), name='reg'),
]
urlpatterns += router.urls

# {
#     "username": "_",
#     "password": "_",
#     "email": "_"
# }