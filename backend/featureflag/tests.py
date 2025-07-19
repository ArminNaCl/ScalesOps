from django.test import TestCase
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from django.db import transaction
from unittest.mock import patch
from .models import FeatureFlag, Dependency, AuditLog
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError  # For unique_together tests

from .models import FeatureFlag, Dependency

User = get_user_model()


class FeatureFlagModelTests(TestCase):
    def setUp(self):
        self.flag_a = FeatureFlag.objects.create(title="flag_a", is_enabled=True)
        self.flag_b = FeatureFlag.objects.create(title="flag_b", is_enabled=True)
        self.flag_c = FeatureFlag.objects.create(title="flag_c", is_enabled=True)
        self.flag_d = FeatureFlag.objects.create(title="flag_d", is_enabled=False)

    def test_feature_flag_creation(self):
        self.assertEqual(FeatureFlag.objects.count(), 4)
        self.assertEqual(self.flag_a.title, "flag_a")
        self.assertTrue(self.flag_a.is_enabled)

    def test_feature_flag_is_active_no_dependencies(self):
        self.assertTrue(self.flag_a.is_active())
        self.assertFalse(self.flag_d.is_active())

    def test_feature_flag_is_active_with_dependencies(self):
        # flag_b depends on flag_a
        Dependency.objects.create(dependent_flag=self.flag_b, source_flag=self.flag_a)

        self.assertTrue(
            self.flag_b.is_active()
        )  # flag_a is enabled, so flag_b should be active

        self.flag_a.is_enabled = False
        self.flag_a.save()
        self.assertFalse(
            self.flag_b.is_active()
        )  # flag_a is disabled, so flag_b should be inactive

    def test_feature_flag_is_active_with_multiple_dependencies(self):
        # flag_c depends on flag_a and flag_b
        Dependency.objects.create(dependent_flag=self.flag_c, source_flag=self.flag_a)
        Dependency.objects.create(dependent_flag=self.flag_c, source_flag=self.flag_b)

        self.assertTrue(self.flag_c.is_active())  # Both flag_a and flag_b are enabled

        self.flag_a.is_enabled = False
        self.flag_a.save()
        self.assertFalse(
            self.flag_c.is_active()
        )  # flag_a is disabled, so flag_c should be inactive

        self.flag_a.is_enabled = True
        self.flag_a.save()
        self.flag_b.is_enabled = False
        self.flag_b.save()
        self.assertFalse(
            self.flag_c.is_active()
        )  # flag_b is disabled, so flag_c should be inactive

    def test_dependency_creation(self):
        dependency = Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_a
        )
        self.assertEqual(dependency.dependent_flag, self.flag_b)
        self.assertEqual(dependency.source_flag, self.flag_a)
        self.assertEqual(Dependency.objects.count(), 1)

    def test_dependency_evaluate(self):
        # flag_b depends on flag_a
        dependency = Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_a
        )
        self.assertTrue(dependency.evaluate())  # flag_a is enabled

        self.flag_a.is_enabled = False
        self.flag_a.save()
        self.assertFalse(dependency.evaluate())  # flag_a is disabled

    def test_audit_log_creation(self):
        user = User.objects.create_user(username="testuser", password="password")
        log = AuditLog.objects.create(
            flag=self.flag_a, creator=user, reason="Created for testing"
        )
        self.assertEqual(log.flag, self.flag_a)
        self.assertEqual(log.creator, user)
        self.assertEqual(log.reason, "Created for testing")
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_audit_log_without_creator(self):
        log = AuditLog.objects.create(flag=self.flag_b, reason="System toggle")
        self.assertEqual(log.flag, self.flag_b)
        self.assertIsNone(log.creator)

    def test_feature_flag_str_representation(self):
        self.assertEqual(str(self.flag_a), "flag_a")

    def test_dependency_str_representation(self):
        dependency = Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_a
        )
        self.assertEqual(str(dependency), "flag_b -> flag_a")

    def test_audit_log_str_representation(self):
        user = User.objects.create_user(username="anotheruser", password="password")
        log = AuditLog.objects.create(
            flag=self.flag_c, creator=user, reason="Some reason"
        )
        # Note: The __str__ method on AuditLog refers to feature_flag.title, not flag.title.
        # This will raise an AttributeError in the current code unless corrected.
        # Assuming you meant `flag.title` for consistency.
        # If not, the test will correctly fail, indicating a bug in your __str__.
        self.assertIn("flag_c", str(log))
        self.assertIn(
            str(log.created_at.year), str(log)
        )  # Check for parts of the datetime

    def test_is_active_with_disabled_flag_and_dependencies(self):
        # flag_b depends on flag_a (both initially enabled)
        Dependency.objects.create(dependent_flag=self.flag_b, source_flag=self.flag_a)
        self.assertTrue(self.flag_b.is_active())

        # Disable flag_b itself, even if flag_a is active, flag_b should be inactive
        self.flag_b.is_enabled = False
        self.flag_b.save()
        self.assertFalse(self.flag_b.is_active())


class DependencyCircularDetectionTests(TestCase):
    def setUp(self):
        self.flag_a = FeatureFlag.objects.create(title="FlagA")
        self.flag_b = FeatureFlag.objects.create(title="FlagB")
        self.flag_c = FeatureFlag.objects.create(title="FlagC")
        self.flag_d = FeatureFlag.objects.create(title="FlagD")
        self.flag_e = FeatureFlag.objects.create(title="FlagE")
        self.flag_f = FeatureFlag.objects.create(title="FlagF")

    def test_no_circular_dependency_on_simple_creation(self):

        try:
            Dependency.objects.create(
                dependent_flag=self.flag_a, source_flag=self.flag_b
            )
            self.assertEqual(Dependency.objects.count(), 1)
        except ValidationError as e:
            self.fail(f"ValidationError unexpectedly raised: {e}")

    def test_prevent_self_dependency(self):
        with self.assertRaisesMessage(
            ValidationError,
            "A feature flag cannot depend on itself. Please select two different flags.",
        ):
            Dependency.objects.create(
                dependent_flag=self.flag_a, source_flag=self.flag_a
            )
        self.assertEqual(Dependency.objects.count(), 0)

    def test_direct_circular_dependency(self):
        """
        Tests that creating A -> B then B -> A is prevented.
        Existing: FlagA -> FlagB
        Attempting: FlagB -> FlagA
        Expected cycle: FlagA -> FlagB -> FlagA
        """
        Dependency.objects.create(dependent_flag=self.flag_a, source_flag=self.flag_b)
        self.assertEqual(Dependency.objects.count(), 1)

        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagB' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagB -> FlagA -> FlagB. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_a
            )

        self.assertEqual(Dependency.objects.count(), 1)

    def test_indirect_circular_dependency_three_flags(self):
        """
        Tests for an indirect circular dependency: A -> B, B -> C, then C -> A.
        Existing: FlagA -> FlagB, FlagB -> FlagC
        Attempting: FlagC -> FlagA
        Expected cycle: FlagC -> FlagA -> FlagB -> FlagC
        """
        Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_b
        )
        Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_c
        )
        self.assertEqual(Dependency.objects.count(), 2)

        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagC' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagC -> FlagA -> FlagB -> FlagC. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_c, source_flag=self.flag_a
            )

        self.assertEqual(
            Dependency.objects.count(), 2
        )

    def test_indirect_circular_dependency_long_chain(self):
        """
        Tests for a longer indirect circular dependency: A -> B, B -> C, C -> D, then D -> A.
        Existing: FlagA -> FlagB, FlagB -> FlagC, FlagC -> FlagD
        Attempting: FlagD -> FlagA
        Expected cycle: FlagD -> FlagA -> FlagB -> FlagC -> FlagD
        """
        Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_b
        )  # A -> B
        Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_c
        )  # B -> C
        Dependency.objects.create(
            dependent_flag=self.flag_c, source_flag=self.flag_d
        )  # C -> D
        self.assertEqual(Dependency.objects.count(), 3)


        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagD' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagD -> FlagA -> FlagB -> FlagC -> FlagD. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_d, source_flag=self.flag_a
            )

        self.assertEqual(
            Dependency.objects.count(), 3
        )  

    def test_no_circular_dependency_on_branching_graph(self):
        """
        Tests that creating dependencies in a branching graph doesn't falsely trigger circularity.
        A -> B
        A -> C
        B -> D
        C -> D
        """
        try:
            Dependency.objects.create(
                dependent_flag=self.flag_a, source_flag=self.flag_b
            )  # A -> B
            Dependency.objects.create(
                dependent_flag=self.flag_a, source_flag=self.flag_c
            )  # A -> C
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_d
            )  # B -> D
            Dependency.objects.create(
                dependent_flag=self.flag_c, source_flag=self.flag_d
            )  # C -> D
            self.assertEqual(Dependency.objects.count(), 4)
        except ValidationError as e:
            self.fail(f"ValidationError unexpectedly raised for valid branching: {e}")

    def test_circular_dependency_with_unrelated_flags(self):
        """
        Ensure detection works correctly even with other unrelated flags present.
        Existing: FlagA -> FlagB
        Existing: FlagC -> FlagD
        Attempting: FlagB -> FlagA
        """
        Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_b
        )  # A -> B
        Dependency.objects.create(
            dependent_flag=self.flag_c, source_flag=self.flag_d
        )  # C -> D (unrelated)
        self.assertEqual(Dependency.objects.count(), 2)

        # Attempt to create the circular dependency
        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagB' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagB -> FlagA -> FlagB. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_a
            )
        self.assertEqual(Dependency.objects.count(), 2)  # Should remain 2 dependencies

    def test_complex_circular_dependency_scenario(self):
        """
        More complex scenario with multiple paths, ensuring correct cycle detection.
        Initial setup:
        FlagA -> FlagB
        FlagB -> FlagC
        FlagA -> FlagD
        FlagD -> FlagE
        Attempt to create FlagE -> FlagA (should create cycle FlagA -> FlagD -> FlagE -> FlagA)
        """
        Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_b
        )  # A -> B
        Dependency.objects.create(
            dependent_flag=self.flag_b, source_flag=self.flag_c
        )  # B -> C
        Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_d
        )  # A -> D
        Dependency.objects.create(
            dependent_flag=self.flag_d, source_flag=self.flag_e
        )  # D -> E
        self.assertEqual(Dependency.objects.count(), 4)

        # Attempt to create FlagE -> FlagA
        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagE' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagE -> FlagA -> FlagD -> FlagE. "  # Note: The path starts from FlagE (the dependent_flag)
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_e, source_flag=self.flag_a
            )
        self.assertEqual(Dependency.objects.count(), 4)

    def test_unique_together_constraint(self):
        """
        Ensures that the unique_together constraint for (dependent_flag, source_flag) works.
        """
        Dependency.objects.create(dependent_flag=self.flag_a, source_flag=self.flag_b)
        self.assertEqual(Dependency.objects.count(), 1)

        with transaction.atomic():
            duplicate_dependency = Dependency(
                dependent_flag=self.flag_a, source_flag=self.flag_b
            )
            with patch.object(
                duplicate_dependency, "full_clean", side_effect=lambda: None
            ):
                with self.assertRaises(IntegrityError) as cm:
                    # Attempt to create the exact same dependency again
                    duplicate_dependency.save()
                self.assertIn(
                    "UNIQUE constraint failed: featureflag_dependency.dependent_flag_id, featureflag_dependency.source_flag_id",
                    str(cm.exception),
                )

        self.assertEqual(
            Dependency.objects.count(), 1
        )  # Still only one unique dependency

    def test_order_of_creation_does_not_matter_for_detection(self):
        """
        Tests that cycle detection is symmetrical regardless of which part of the cycle is added first.
        Scenario 1: A -> B, then try B -> A
        Scenario 2: B -> A, then try A -> B
        """
        # Scenario 1: A -> B already exists
        Dependency.objects.create(dependent_flag=self.flag_a, source_flag=self.flag_b)

        # We need a new flag for this, let's use FlagC for the second part of the test
        # Let's make it simpler and use FlagF for the symmetric test
        self.flag_f = FeatureFlag.objects.create(title="FlagF_Symmetric")

        # Test A -> F, then F -> A
        Dependency.objects.create(dependent_flag=self.flag_a, source_flag=self.flag_f)

        with self.assertRaises(ValidationError):
            Dependency.objects.create(
                dependent_flag=self.flag_f, source_flag=self.flag_a
            )

        # Clean up for next symmetric test
        Dependency.objects.all().delete()

        # Scenario 2: F -> A already exists
        Dependency.objects.create(dependent_flag=self.flag_f, source_flag=self.flag_a)
        with self.assertRaises(ValidationError):
            Dependency.objects.create(
                dependent_flag=self.flag_a, source_flag=self.flag_f
            )

    def test_deletion_breaks_cycle(self):
        """
        Tests that deleting a dependency correctly breaks a cycle, allowing subsequent additions.
        A -> B, B -> A (prevented)
        Delete A -> B
        Then allow B -> A
        """
        # Create A -> B
        dep_ab = Dependency.objects.create(
            dependent_flag=self.flag_a, source_flag=self.flag_b
        )

        # Attempt B -> A (should fail)
        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagB' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagB -> FlagA -> FlagB. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_a
            )

        # Delete A -> B
        dep_ab.delete()
        self.assertEqual(Dependency.objects.count(), 0)

        # Now, B -> A should be allowed
        try:
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_a
            )
            self.assertEqual(Dependency.objects.count(), 1)
        except ValidationError as e:
            self.fail(f"ValidationError unexpectedly raised after breaking cycle: {e}")

    def test_inactive_flags_still_cause_dependency_conflict(self):
        """
        Tests that circular dependency detection considers the graph structure,
        regardless of whether flags are currently active or not.
        """
        self.flag_a.is_enabled = False
        self.flag_a.save()
        self.flag_b.is_enabled = False
        self.flag_b.save()

        Dependency.objects.create(dependent_flag=self.flag_a, source_flag=self.flag_b)

        expected_message = (
            "This dependency creates a circular relationship. "
            "Adding 'FlagB' depending on 'FlagA' "
            "would form a direct or indirect cycle: FlagB -> FlagA -> FlagB. "
            "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
        )
        with self.assertRaisesMessage(ValidationError, expected_message):
            Dependency.objects.create(
                dependent_flag=self.flag_b, source_flag=self.flag_a
            )

        self.assertEqual(Dependency.objects.count(), 1)
