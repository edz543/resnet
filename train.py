import torch
from torch import nn
from torch.optim.lr_scheduler import MultiStepLR
from torchvision import transforms
import wandb

from dataloader import get_dataloader
from resnet import ResNet

# Ensure deterministic behavior
torch.backends.cudnn.deterministic = True
torch.manual_seed(42)
torch.cuda.manual_seed(42)

# Device configuration
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def make(config):
    train_transform = transforms.Compose(
        [
            transforms.ToTensor(),
            # Paper uses per-pixel mean subtraction
            # I use PyTorch's normalization
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            transforms.RandomCrop(32, padding=4),
        ]
    )
    train_dataloader, test_dataloader = get_dataloader(
        train_transform, transforms.ToTensor(), config.batch_size
    )

    model = ResNet(config.n).to(device)

    loss_func = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        momentum=config.momentum,
    )
    scheduler = MultiStepLR(optimizer, milestones=[82, 123], gamma=0.1)

    return (
        model,
        train_dataloader,
        test_dataloader,
        loss_func,
        optimizer,
        scheduler,
    )


def evaluate(model, loader, loss_func):
    model.eval()
    loss_sum = 0.0
    with torch.inference_mode():
        correct = 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)

            # Forward pass
            outputs = model(images)
            loss_sum += loss_func(outputs, labels) * labels.size(0)

            _, predicted_indices = torch.max(outputs.data, 1)
            correct += (predicted_indices == labels).sum().item()

    loss = loss_sum / len(loader.dataset)
    accuracy = correct / len(loader.dataset)

    return loss, accuracy


def train(model, train_loader, test_loader, loss_func, optimizer, scheduler, config):
    # Tell wandb to watch what the model gets up to: gradients, weights, and more!
    wandb.watch(model, loss_func, log="all", log_freq=10)

    for epoch in range(config.epochs):
        model.train()

        # Train for one epoch
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            outputs = model(images)
            train_loss = loss_func(outputs, labels)
            optimizer.zero_grad()
            train_loss.backward()
            optimizer.step()

        # Log training and testing metrics
        train_loss, train_accuracy = evaluate(model, train_loader, loss_func)
        test_loss, test_accuracy = evaluate(model, test_loader, loss_func)
        wandb.log(
            {
                "epoch": epoch,
                "train/error": 1 - train_accuracy,
                "train/loss": train_loss,
                "test/error": 1 - test_accuracy,
                "test/loss": test_loss,
            }
        )

        # Adjust learning rate
        scheduler.step()


def model_pipeline(project, config):

    # tell wandb to get started
    with wandb.init(project=project, config=dict(config)) as run:
        # access all HPs through wandb.config, so logging matches execution!
        config = wandb.config

        # make the model, data, optimizer, and scheduler
        (
            model,
            train_loader,
            test_loader,
            loss_func,
            optimizer,
            scheduler,
        ) = make(config)

        # and use them to train the model
        train(model, train_loader, test_loader, loss_func, optimizer, scheduler, config)

        # Save model weights
        model_artifact = wandb.Artifact(
            "resnet",
            type="model",
            description="Residual Neural Network model trained on CIFAR-10 dataset.",
            metadata=dict(config),
        )

        torch.save(model.state_dict(), "model.pth")

        wandb.save("model.pth")

        run.log_artifact(model_artifact)


# Execute training pipeline
if __name__ == "__main__":
    wandb.login()

    hyperparameters = {
        "n": 3,
        "batch_size": 128,
        "learning_rate": 0.1,
        "epochs": 164,
        "weight_decay": 0.0001,
        "momentum": 0.9,
    }

    model_pipeline("resnet", hyperparameters)
