# Деплой pipeline в Kubernetes

Проект деплоится как Kubernetes Job: контейнер запускает финальный CLI-пайплайн,
пишет результаты в `/app/output` и завершается.

## 1. Сборка и публикация образа

Замените `your-dockerhub-user` на свой Docker Hub namespace:

```bash
docker build -t your-dockerhub-user/vkr-pipeline:latest .
docker push your-dockerhub-user/vkr-pipeline:latest
```

После этого замените image в `k8s/job.yaml`:

```yaml
image: docker.io/your-dockerhub-user/vkr-pipeline:latest
```

## 2. Подключение к кластеру

```bash
export KUBECONFIG=/path/to/kubeconfig
kubectl get nodes
```

Если нужно работать в отдельном namespace:

```bash
kubectl create namespace vkr
kubectl config set-context --current --namespace=vkr
```

## 3. Secret с API-ключом

Не коммитьте реальный ключ. Создайте secret командой:

```bash
kubectl create secret generic vkr-pipeline-secrets \
  --from-literal=TOGETHER_API_KEY='ваш-ключ'
```

Файл `k8s/secret.example.yaml` нужен только как пример структуры.

## 4. Persistent volume для результатов

```bash
kubectl apply -f k8s/pvc.yaml
kubectl get pvc
```

Результаты пайплайна будут писаться в `/app/output` внутри контейнера,
а фактически сохраняться в PVC `vkr-pipeline-output`.

## 5. Запуск Job

```bash
kubectl apply -f k8s/job.yaml
kubectl get jobs
kubectl logs job/vkr-pipeline -f
```

По умолчанию Job запускает:

```bash
python -m pipeline.run_unified conspect --all --output-dir /app/output
```

Чтобы запустить другой режим, измените `args` в `k8s/job.yaml`.
Например, геометрическая задача из корпуса:

```yaml
args:
  - geometry
  - --slug
  - task14_pyramid_apex_to_face
  - --animated
  - --output-dir
  - /app/output
```

## 6. Повторный запуск

Kubernetes Job с тем же именем нельзя применить повторно без удаления старого:

```bash
kubectl delete job vkr-pipeline
kubectl apply -f k8s/job.yaml
```
