# How to use Mealie

In-depth information on how to use Mealie can be found at https://docs.mealie.io/documentation/getting-started/features/.

## Getting Started

1. Go to the Mealie webpage at the address you set up during deployment. To find it again, you can use the command ```kubectl get svc --namespace INSERT_MEALIE_NAMESPACE``` to find the service URL.
2. Log in with the default credentials (changeme@example.com / MyPassword).
3. Enter in your account details. Enable advanced content. Continue
4. Enable Seed Data under Data Management to make importing recipes later easier. Continue.
5. Review all your information and continue.
6. You can now import recipes, create meal plans, and explore Mealie's features.

## Importing a recipe

Mealie can import recipes from most recipe websites out of the box. However, certain websites like Reddit are unsupported. If you have enabled OpenAI integration, you can use the AI-powered extraction tool within Mealie to assist with parsing recipes from unsupported sites. This feature can help automatically extract ingredients and instructions. To import a recipe from a URL:

1. Under your username in the top left corner of the website, click create.
2. Click import.
3. Copy and paste the URL into the Recipe URL box.
4. Click stay in edit mode and click create. The recipe will be imported. But you need to parse the ingredients for it to make sense.
5. Click the settings button under description and click disable ingredients amounts.
6. Under the ingredients section, click the parse button. It will have an apple symbol. The ingredients will be parsed by the Natural Language Processor by default. If you have enabled OpenAI integration, you can also choose to use the AI parser by selecting it from the dropdown menu next to the parse button. This may provide better results for complex or unusual ingredient lists.
7. Click the create missing food buttons if the ingredients are not already in your database. If the food is nonsensical, click the choose food box and manually enter in the desired food and add it to the database, or select an already existing food.
8. When you are done parsing ingredients. Click save at the top right corner.
9. Your recipe is now imported and ready to use. You can further edit the recipe details, add images, or categorize it as needed. Lastly, you are now able to change the serving number and associated ingredient quantities accordingly.

## Testing OpenAI functionality

OpenAI is not enabled out of the box. You need to make an OpenAI account or set up Open Web UI to run your models locally. To enable OpenAI you need input your OpenAPI key in the mealie environment variables in the values.yaml file, or make a Kubernetes secret (https://kubernetes.io/docs/concepts/configuration/secret/). The base URL is set for OpenAI's servers by default and must be changed if you are running your models locally. To test if your configuration is working properly, you can do the following steps. Advanced mode must be enabled during setup.

1. Click the settings button in mealie on the bottom left corner of the sidebar.
2. Select Debug on the sidebar.
3. Select OpenAI on the sidebar.
4. Optionally upload an image of a food for OpenAI to test to see if image recognition is functioning properly. This only works if the model you have chosen has image recognition functionality.
5. Click Run Test.
6. The results of the test will be displayed below.

## Backup and Restore

If anything happens to your database, you can restore it from a backup using the Backups page in the settings menu. However, if you are using Postgres, then it is more difficult to restore your data. Before restoring a backup using a Postgres database, you need to make the Postgres user a Superuser first. More information can be found at https://docs.mealie.io/documentation/getting-started/usage/backups-and-restoring/.
