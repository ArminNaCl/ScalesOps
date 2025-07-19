"""
JUST PROTOTYPE
"""
# TODO ADD CELERY and CELERY BEAT
# NOTE TEST SHOULD INCLUDE


from .models import FeatureFlag



def auto_disabler():
    seen = set()
    root_flags = FeatureFlag.objects.filter(dependency_rules_as_dependent__count=0, is_enabled=False)
    for flag in root_flags:
        disable_all_children(flag.pk,seen)

    

def disable_all_children(pk:int, seen):
    flag = FeatureFlag.objects.get(id=pk)
    children = flag.dependency_rules_as_source.exclude(id__in=seen)
    seen.append(pk)
    # ADD AUDIT LOG AUTO DISABLE
    children.objects.update(is_enabled=False)
    for child in children:
        disable_all_children(pk=child.id, seen)
    