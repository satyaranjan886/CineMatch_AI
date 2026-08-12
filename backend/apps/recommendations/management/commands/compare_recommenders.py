from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from ml.evaluation.report import comparison_to_json, format_comparison_table
from ml.pipelines.evaluation import run_recommender_comparison


class Command(BaseCommand):
    help = "Compare popularity, content-based, collaborative, and hybrid recommenders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            type=str,
            nargs="+",
            default=None,
            help="Optional subset of models to compare.",
        )
        parser.add_argument(
            "--split",
            type=str,
            default="temporal_leave_one_out",
            choices=["temporal_leave_one_out", "temporal_cutoff"],
            help="Dataset split strategy.",
        )
        parser.add_argument(
            "--cutoff",
            "--cutoff-date",
            dest="cutoff",
            type=str,
            default=None,
            help="ISO timestamp cutoff for temporal_cutoff split (alias: --cutoff-date).",
        )
        parser.add_argument(
            "--k",
            type=int,
            nargs="+",
            default=None,
            help="K values for metrics (default includes 5 and 10).",
        )
        parser.add_argument(
            "--min-interactions",
            type=int,
            default=None,
            help="Minimum interactions required for a user to enter personalized evaluation.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible ALS / sampling.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Recommendation list length generated per user.",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["table", "json"],
            default="table",
            help="Output format.",
        )
        parser.add_argument(
            "--no-persist",
            action="store_true",
            help="Do not store the comparison report in the database.",
        )

    def handle(self, *args, **options):
        cutoff = None
        if options["split"] == "temporal_cutoff":
            if not options["cutoff"]:
                raise CommandError("--cutoff / --cutoff-date is required for temporal_cutoff.")
            cutoff = parse_datetime(options["cutoff"])
            if cutoff is None:
                raise CommandError("Invalid --cutoff / --cutoff-date timestamp.")

        report = run_recommender_comparison(
            model_names=options["models"],
            split=options["split"],
            cutoff=cutoff,
            k_values=options["k"],
            recommendation_limit=options["limit"],
            min_interactions=options["min_interactions"],
            seed=options["seed"],
            persist=not options["no_persist"],
        )

        if options["format"] == "json":
            self.stdout.write(comparison_to_json(report))
        else:
            self.stdout.write(format_comparison_table(report))

        if not report.sufficient_data:
            self.stderr.write(
                self.style.WARNING(report.notes or "Insufficient data for comparison.")
            )
