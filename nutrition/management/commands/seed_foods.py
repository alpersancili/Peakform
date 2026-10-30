from django.core.management.base import BaseCommand

from nutrition.models import Food

# name, serving_size, serving_unit, calories, protein_g, carbs_g, fat_g
# Approximate values for common foods; curated (created_by=None), shared
# across all users as a starting catalog for food search.
COMMON_FOODS = [
    ("Chicken breast, cooked", 100, "g", 165, 31, 0, 3.6),
    ("Chicken thigh, cooked", 100, "g", 209, 26, 0, 10.9),
    ("Salmon, cooked", 100, "g", 208, 20, 0, 13),
    ("Lean ground beef, cooked", 100, "g", 217, 26, 0, 12),
    ("Egg, whole", 1, "piece", 72, 6.3, 0.4, 4.8),
    ("Egg white", 1, "piece", 17, 3.6, 0.2, 0.1),
    ("Greek yogurt, plain nonfat", 100, "g", 59, 10, 3.6, 0.4),
    ("Cottage cheese, low-fat", 100, "g", 81, 11, 3.4, 2.3),
    ("Whey protein powder", 30, "g", 120, 24, 3, 1.5),
    ("Tofu, firm", 100, "g", 144, 15.5, 2.8, 8.7),
    ("White rice, cooked", 100, "g", 130, 2.7, 28, 0.3),
    ("Brown rice, cooked", 100, "g", 123, 2.7, 25.6, 1),
    ("Oats, dry", 40, "g", 150, 5.3, 27, 2.7),
    ("Quinoa, cooked", 100, "g", 120, 4.4, 21, 1.9),
    ("Whole wheat bread", 1, "slice", 81, 4, 14, 1.1),
    ("Sweet potato, baked", 100, "g", 90, 2, 21, 0.1),
    ("Potato, baked", 100, "g", 93, 2.5, 21, 0.1),
    ("Pasta, cooked", 100, "g", 131, 5, 25, 1.1),
    ("Banana", 1, "piece", 105, 1.3, 27, 0.4),
    ("Apple", 1, "piece", 95, 0.5, 25, 0.3),
    ("Orange", 1, "piece", 62, 1.2, 15.4, 0.2),
    ("Blueberries", 100, "g", 57, 0.7, 14.5, 0.3),
    ("Broccoli, steamed", 100, "g", 35, 2.4, 7.2, 0.4),
    ("Spinach, raw", 100, "g", 23, 2.9, 3.6, 0.4),
    ("Mixed salad greens", 100, "g", 17, 1.5, 3, 0.2),
    ("Avocado", 100, "g", 160, 2, 8.5, 14.7),
    ("Almonds", 30, "g", 174, 6.4, 6.1, 15),
    ("Peanut butter", 32, "g", 190, 8, 6, 16),
    ("Olive oil", 1, "tbsp", 119, 0, 0, 13.5),
    ("Whole milk", 240, "ml", 149, 7.7, 11.7, 8),
    ("Skim milk", 240, "ml", 83, 8.3, 12.2, 0.2),
    ("Black beans, cooked", 100, "g", 132, 8.9, 23.7, 0.5),
    ("Lentils, cooked", 100, "g", 116, 9, 20, 0.4),
    ("Protein bar", 1, "piece", 200, 20, 22, 7),
]


class Command(BaseCommand):
    help = "Seed the shared food catalog with common foods for search/logging."

    def handle(self, *args, **options):
        created = 0
        for name, size, unit, cal, protein, carbs, fat in COMMON_FOODS:
            _, was_created = Food.objects.get_or_create(
                name=name,
                created_by=None,
                defaults={
                    "serving_size": size,
                    "serving_unit": unit,
                    "calories": cal,
                    "protein_g": protein,
                    "carbs_g": carbs,
                    "fat_g": fat,
                },
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new foods ({len(COMMON_FOODS)} total in catalog)."))
