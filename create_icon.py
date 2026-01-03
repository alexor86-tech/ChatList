from PIL import Image, ImageDraw

def draw_icon(size):
    """Рисует синий круг в красном квадрате."""
    # Создаем RGB изображение с красным фоном
    img = Image.new("RGB", (size, size), (220, 20, 60))  # Crimson - красный фон
    draw = ImageDraw.Draw(img)
    
    # Вычисляем размеры с отступами (10% от размера с каждой стороны)
    padding = int(size * 0.1)
    circle_size = size - (padding * 2)
    
    # Координаты для круга (центрированный)
    center_x = size // 2
    center_y = size // 2
    radius = circle_size // 2
    
    # Рисуем синий круг
    circle_coords = [
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius
    ]
    
    # Синий цвет (DodgerBlue)
    blue_color = (30, 144, 255)
    draw.ellipse(circle_coords, fill=blue_color)
    
    return img

# Размеры иконки
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
icons = [draw_icon(s) for s, _ in sizes]

# Изображения уже в RGB режиме, просто убеждаемся
rgb_icons = []
for icon in icons:
    # Убеждаемся, что изображение в RGB режиме (не палитра)
    if icon.mode != "RGB":
        rgb_img = icon.convert("RGB")
    else:
        rgb_img = icon
    rgb_icons.append(rgb_img)

# Сохранение с явным указанием формата и цветов
# ВАЖНО: Изображения уже в RGB режиме с красным фоном, что гарантирует
# сохранение цветов и избегает автоматической конвертации в градации серого
try:
    rgb_icons[0].save(
        "app.ico",
        format="ICO",
        sizes=sizes,
        append_images=rgb_icons[1:]
    )
    print("✅ Иконка 'app.ico' создана!")
    print("   Дизайн: синий круг в красном квадрате")
    print("   Цвета: красный фон (Crimson), синий круг (DodgerBlue)")
except Exception as e:
    print(f"❌ Ошибка при сохранении: {e}")
    # Альтернативный способ - сохранить каждое изображение отдельно
    print("Попытка альтернативного метода сохранения...")
    rgb_icons[0].save("app.ico", format="ICO")
    print("✅ Иконка 'app.ico' создана (только один размер)")