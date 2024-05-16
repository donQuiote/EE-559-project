import os
import torch
from torch.optim import AdamW
from Models import create_student_model, create_teacher_model
from Datasets_Batches import Spliter, prepare_data_loader
from Data_Handler import setup_data
from transformers import BertTokenizer, get_scheduler
from Running import load_metrics, trainer_distiller

#OUR_TARGET = ["women", "jews", "asian", "black", "lgbtq", "latino", "muslim", "indigenous", "arab", "others", "disabilities"]
OUR_TARGET = ["women"]
missing_data = False
save = True

def main():
    if not os.path.exists("Data") or not os.listdir("Data"):
        setup_data()

    #define a dictionary linking a student model to a specific target
    target_models = {target: create_student_model(num_classes=2) for target in OUR_TARGET}

    # Generate the dictionary to find the file
    datasets = {
        target: {"hate": f"Data/hate_{target}.csv", "neutral": f"Data/neutral_{target}.csv"} for
        target in OUR_TARGET}

    #Create the teacher_model
    teacher_model = create_teacher_model()

    #Create the tokenizer
    tokenizer = BertTokenizer.from_pretrained("hate_bert")

    # train student model
    for target in OUR_TARGET:
        #generate the training and testing data paths
        hate_target = datasets[target]["hate"]
        neutral_target = datasets[target]["neutral"]

        #Fetch the data and split it into test and training
        train_data, test_data = Spliter(hate_target,neutral_target, tokenizer, test_size=0.2, random_state=42)

        # Prepare data loaders
        train_loader, test_loader = prepare_data_loader(train_data, test_data, batch_size=32)

        # Define optimizer, criterion, and device
        optimizer = AdamW(target_models[target].parameters(), lr=5e-5)
        metrics = load_metrics("accuracy", "f1")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        num_epochs = 2
        alpha = 0.25
        temperature = 2
        num_training_steps = num_epochs * len(train_loader)
        # feel free to experiment with different num_warmup_steps
        lr_scheduler = get_scheduler(name="linear", optimizer=optimizer, num_warmup_steps=1, num_training_steps=num_training_steps)

        # Train the student model with distillation
        print("Start training for ",target)
        train_loss_log, test_loss_log, distil_loss_log, train_metric_scores, test_metric_scores = trainer_distiller(student_model=target_models[target], teacher_model=teacher_model, optimizer=optimizer, nbr_steps=num_training_steps, lr_scheduler=lr_scheduler, metrics=metrics, train_loader=train_loader,
                          test_loader=test_loader, nbr_epochs=num_epochs, device=device, alpha=alpha, T= temperature, tokenizer=tokenizer)

        print(train_loss_log, test_loss_log, distil_loss_log, train_metric_scores, test_metric_scores)

        # Save logs
        if save:
            log_file = os.path.join("logs_and_weights", f"{target}_log.txt")
            with open(log_file, 'w') as f:
                f.write(f"Train Metrics Log:\n{train_metric_scores}\n\nTest Metrics Log:\n{test_metric_scores}\nTrain losses Log:\n{train_loss_log}\nDistillation losses Log:\n{distil_loss_log}\nTest losses Log:\n{test_loss_log}")

            # Save model weights
            weights_file = os.path.join("logs_and_weights", f"{target}_weights.pth")
            torch.save(target_models[target].state_dict(), weights_file)


if __name__ == '__main__':
    main()
