from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.permissions import IsStaffUser
from apps.experiments.lifecycle import pause_experiment, start_experiment, stop_experiment
from apps.experiments.metrics import compute_experiment_results
from apps.experiments.models import Experiment
from apps.experiments.registry import list_model_keys
from apps.experiments.serializers import ExperimentResultsSerializer, ExperimentSerializer


class ExperimentListCreateView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: ExperimentSerializer(many=True)})
    def get(self, request):
        experiments = Experiment.objects.all()
        return Response(ExperimentSerializer(experiments, many=True).data)

    @extend_schema(request=ExperimentSerializer, responses={201: ExperimentSerializer})
    def post(self, request):
        serializer = ExperimentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        experiment = serializer.save()
        return Response(ExperimentSerializer(experiment).data, status=status.HTTP_201_CREATED)


class ExperimentDetailView(APIView):
    permission_classes = [IsStaffUser]

    def get_object(self, pk) -> Experiment:
        return Experiment.objects.get(pk=pk)

    @extend_schema(responses={200: ExperimentSerializer})
    def get(self, request, pk):
        try:
            experiment = self.get_object(pk)
        except Experiment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExperimentSerializer(experiment).data)


class ExperimentStartView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: ExperimentSerializer})
    def post(self, request, pk):
        try:
            experiment = Experiment.objects.get(pk=pk)
            experiment = start_experiment(experiment)
        except Experiment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExperimentSerializer(experiment).data)


class ExperimentStopView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: ExperimentSerializer})
    def post(self, request, pk):
        try:
            experiment = Experiment.objects.get(pk=pk)
            experiment = stop_experiment(experiment)
        except Experiment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExperimentSerializer(experiment).data)


class ExperimentPauseView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: ExperimentSerializer})
    def post(self, request, pk):
        try:
            experiment = Experiment.objects.get(pk=pk)
            experiment = pause_experiment(experiment)
        except Experiment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ExperimentSerializer(experiment).data)


class ExperimentResultsView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: ExperimentResultsSerializer})
    def get(self, request, pk):
        try:
            experiment = Experiment.objects.get(pk=pk)
        except Experiment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(compute_experiment_results(experiment))


class ExperimentModelCatalogView(APIView):
    permission_classes = [IsStaffUser]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"models": list_model_keys()})
