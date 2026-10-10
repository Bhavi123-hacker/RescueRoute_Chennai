"""Create an operator without echoing or passing passwords on the command line."""
import argparse
import getpass
if __name__ == "__main__":
    import boto3
    p = argparse.ArgumentParser()
    p.add_argument("--stack", default="rescueroute-chennai")
    p.add_argument("--region", default="eu-north-1")
    p.add_argument("--username", default="dispatcher")
    a = p.parse_args()
    session = boto3.Session(region_name=a.region)
    outputs = session.client("cloudformation").describe_stacks(StackName=a.stack)["Stacks"][0]["Outputs"]
    pool = next(x["OutputValue"] for x in outputs if x["OutputKey"] == "UserPoolId")
    password = getpass.getpass("Operator password (12+ characters, upper/lower case, number, symbol): ")
    client = session.client("cognito-idp")
    try:
        client.admin_create_user(UserPoolId=pool, Username=a.username, MessageAction="SUPPRESS")
    except client.exceptions.UsernameExistsException:
        pass
    client.admin_set_user_password(UserPoolId=pool, Username=a.username, Password=password, Permanent=True)
    print("Operator ready. Sign in on the website with username:", a.username)
