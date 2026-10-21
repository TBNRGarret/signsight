"""
Traffic Sign Recognition Model Architecture
Implements a lightweight custom CNN and MobileNetV3-Small classifier.
Designed for low inference latency (<20ms) and high accuracy on 10 Vietnam classes.
"""

try:
    import torch.nn as nn
    import torchvision.models as models

    class TrafficSignCNN(nn.Module):
        """
        Lightweight custom ConvNet tailored for 64x64 traffic sign images.
        """
        def __init__(self, num_classes: int = 10, *args, **kwargs):
            super().__init__()
            self.num_classes = num_classes
            self.features = nn.Sequential(
                # Block 1
                nn.Conv2d(3, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.Conv2d(32, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2, 2),  # 32x32
                nn.Dropout2d(0.2),

                # Block 2
                nn.Conv2d(32, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.Conv2d(64, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2, 2),  # 16x16
                nn.Dropout2d(0.25),

                # Block 3
                nn.Conv2d(64, 128, kernel_size=3, padding=1),
                nn.BatchNorm2d(128),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2, 2),  # 8x8
                nn.Dropout2d(0.3),
            )
            self.classifier = nn.Sequential(
                nn.Flatten(),
                nn.Linear(128 * 8 * 8, 256),
                nn.BatchNorm1d(256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.4),
                nn.Linear(256, num_classes)
            )

        def forward(self, x):
            x = self.features(x)
            x = self.classifier(x)
            return x

    def get_mobilenet_model(num_classes: int = 10, pretrained: bool = True, *args, **kwargs):
        """
        Transfer learning option with MobileNetV3-Small.
        """
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=weights)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, num_classes)
        return model

except ImportError:
    class TrafficSignCNN:
        def __init__(self, num_classes: int = 10, *args, **kwargs):
            self.num_classes = num_classes

    def get_mobilenet_model(num_classes: int = 10, *args, **kwargs):
        return None
