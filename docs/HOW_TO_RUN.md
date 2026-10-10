# How to run RescueRoute Chennai

## Local demo (Windows CMD)

```bat
cd /d E:\RescueRoute_Chennai
py local_server.py
```

Open **http://localhost:8020** and press **Ctrl+F5**.

If `py` fails:

```bat
cd /d E:\RescueRoute_Chennai
python local_server.py
```

## Optional: retrain ML

```bat
cd /d E:\RescueRoute_Chennai
python -m pip install -r ml\requirements.txt
python ml\train.py
```

## Optional: tests

```bat
cd /d E:\RescueRoute_Chennai
python -m unittest discover -s tests -v
```

## Field usage (after server is running)

1. Click **SOS · nearest hospital now** (uses GPS) or click the map for pickup.
2. Leave hospital on **Auto** or pick one from suggestions.
3. Click **Find shortest way**.
4. Use **Navigate in Google Maps**, **Call hospital**, **Share trip**, **Copy summary**, or **Print card**.
5. Add scene notes / callback number (saved in your browser only).

## AWS deploy (when credentials are configured on your PC)

Do not paste secret keys into chat. On your machine:

```bat
cd /d E:\RescueRoute_Chennai
aws configure
aws sts get-caller-identity
sam build
sam deploy --guided --stack-name rescueroute-chennai
python -m pip install -r requirements-aws.txt
python scripts\publish_frontend.py --stack rescueroute-chennai --region YOUR_REGION
python scripts\setup_user.py --stack rescueroute-chennai --region YOUR_REGION --username dispatcher
```

Set `EnableLocation=true` during deploy for live Amazon Location traffic and Places search.
