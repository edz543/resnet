"""Main ResNet model implementation."""

from torch import nn
import torch.nn.functional as F


class ResidualBlock(nn.Module):
    """
    Residual block with 2 convolutions and a skip connection,
    as described in Figure 2 of the paper
    """

    def __init__(self, num_filters, subsample=False):
        super().__init__()
        self.subsample = subsample

        if subsample:
            self.conv1 = nn.Conv2d(num_filters // 2, num_filters, 3, 2, 1)
        else:
            self.conv1 = nn.Conv2d(num_filters, num_filters, 3, 1, 1)

        self.conv2 = nn.Conv2d(num_filters, num_filters, 3, 1, 1)

        # The paper uses option A for the shortcut connection, I use option B
        self.projection_shortcut = nn.Conv2d(num_filters // 2, num_filters, 1, 2, 0)

    def forward(self, x):
        """Feed forward step"""

        out = self.conv1(x)
        out = F.relu(out)
        out = self.conv2(out)

        # Apply projection shortcut if input and output dimensions don't match
        if self.subsample:
            x = self.projection_shortcut(x)

        # Residual connection
        out += x

        out = F.relu(out)
        return out


class ResNet(nn.Module):
    """ResNet model, as described in CIFAR-10 section of the paper."""

    def __init__(self, n):
        super().__init__()

        self.conv1 = nn.Conv2d(3, 16, 3, 1, 1)

        # Stack of residual blocks with map size 32 and 16 filters
        self.stack1 = nn.Sequential(*[ResidualBlock(16) for _ in range(n)])

        # Stack of residual blocks with map size 16 and 32 filters
        self.stack2 = nn.Sequential(
            ResidualBlock(32, subsample=True),
            *[ResidualBlock(32) for _ in range(n - 1)]
        )

        # Stack of residual blocks with map size 64 and 8 filters
        self.stack3 = nn.Sequential(
            ResidualBlock(64, subsample=True),
            *[ResidualBlock(64) for _ in range(n - 1)]
        )

        self.global_avg_pool = nn.AvgPool2d(8)
        self.fully_connected = nn.Linear(64, 10)

    def forward(self, x):
        """Feed forward step"""

        out = self.conv1(x)
        out = F.relu(out)
        out = self.stack1(out)
        out = self.stack2(out)
        out = self.stack3(out)
        out = self.global_avg_pool(out)
        out = out.view(-1, 64)
        out = self.fully_connected(out)
        return out
