![](https://github.com/5hojib/5hojib/raw/main/images/Aeon-MLTB.gif)

---

# Aeon Bot

Aeon is a streamlined and feature-rich bot designed for efficient deployment and enhanced functionality.

---

## Features

- **Minimalistic and Optimized**: Simplified by removing unnecessary code for better performance.
- **Effortless Deployment**: Fully configured for quick and easy deployment to Heroku.
- **Enhanced Capabilities**: Integrates features from multiple sources to provide a versatile bot experience.

---

## Deployment Instructions (Heroku)

Follow these steps to deploy Aeon to Heroku:

### 1. Fork and Star the Repository
- Click the **Fork** button at the top-right corner of this repository.
- Give the repository a star to show your support.

### 2. Navigate to Your Forked Repository
- Access your forked version of this repository.

### 3. Enable GitHub Actions
- Go to the **Settings** tab of your forked repository.
- Enable **Actions** by selecting the appropriate option in the settings.

### 4. Run the Deployment Workflow
1. Open the **Actions** tab.
2. Select the `Deploy to Heroku` workflow from the available list.
3. Click **Run workflow** and fill out the required inputs:
   - **BOT_TOKEN**: Your Telegram bot token.
   - **OWNER_ID**: Your Telegram ID.
   - **DATABASE_URL**: MongoDB connection string.
   - **TELEGRAM_API**: Telegram API ID (from [my.telegram.org](https://my.telegram.org/)).
   - **TELEGRAM_HASH**: Telegram API hash (from [my.telegram.org](https://my.telegram.org/)).
   - **HEROKU_APP_NAME**: Name of your Heroku app.
   - **HEROKU_EMAIL**: Email address associated with your Heroku account.
   - **HEROKU_API_KEY**: API key from your Heroku account.
   - **HEROKU_TEAM_NAME** (Optional): Required only if deploying under a Heroku team account.
4. Run the workflow and wait for it to complete.

### 5. Finalize Setup
- After deployment, configure any remaining variables in your Heroku dashboard.
- Use the `/botsettings` command to upload sensitive files like `token.pickle` if needed.

---

## Deployment Instructions (VPS)

Follow these steps to deploy Aeon to VPS:

### 1. Star the Repository
- Give the repository a star to show your support.

### 2. Clone The Repository
- Clone the repository to your VPS.

```
git clone https://github.com/AeonOrg/Aeon-MLTB.git && cd Aeon-MLTB
```

### 3. Install Requirements

- For Debian based distros

```
sudo apt install python3 python3-pip
```

Install Docker by following the [official Docker docs](https://docs.docker.com/engine/install/debian/)

- For Arch and it's derivatives:

```
sudo pacman -S docker python
```

- Install dependencies for running setup scripts:

```
pip3 install -r dev/requirements-cli.txt
```

### 4. Setting up config file

```
cp config_sample.py config.py
```

Fill up all the required fields.


### 5. Run the bot

#### Using Docker Compose Plugin

- Install docker compose plugin

```
sudo apt install docker-compose-plugin
```

- Build and run Docker image:

```
sudo docker compose up
```

- After editing files with nano, for example (nano start.sh) or git pull you must use --build to edit container files:

```
sudo docker compose up --build
```

- To stop the running container:

```
sudo docker compose stop
```

- To run the container:

```
sudo docker compose start
```

- To get log from already running container (after mounting the folder):

```
sudo docker compose logs --follow
```

#### Using Official Docker Commands

- Build Docker image:

```
sudo docker build . -t aeon-mltb
```

- Run the image:

```
sudo docker run --network host aeon-mltb
```

- To stop the running image:

```
sudo docker ps
```

```
sudo docker stop id
```

### 6. Open Required Ports:

1. Open all required ports using the shell script:

- Give execute permission & Run the script:

```
sudo chmod +x open_ports.sh
```

```
sudo ./open_ports.sh
```

2. Set `BASE_URL_PORT` and `RCLONE_SERVE_PORT` variables to any port you want to use. Default is `80` and `8080`
   respectively.

3. Check the number of processing units of your machine with `nproc` cmd and times it by 4, then
   edit `AsyncIOThreadsCount` in qBittorrent.conf or while bot working from bsetting->qbittorrent settings.

---

## Contributing

We welcome contributions! Whether it's bug fixes, feature enhancements, or general improvements:
- **Report issues**: Open an issue for bugs or suggestions.
- **Submit pull requests**: Share your contributions with the community.

---

# Aeon-MLTB Docker Build Guide

## Usage

1. **Run the Workflow**  
   - Go to the **Actions** tab in your repository.
   - Select **Docker.io** workflow.
   - Click **Run workflow** and provide:
     - **Docker Hub Username**
     - **Docker Hub Password**
     - **Docker Image Name**

2. **Result**  
   Your Docker image will be available at:  
   `docker.io/<username>/<image_name>:latest`.

## Inputs

| Input        | Description                        |
|--------------|------------------------------------|
| `username`   | Your Docker Hub username           |
| `password`   | Your Docker Hub password           |
| `image_name` | Name of the Docker image to build  |

## Notes

- **Platforms**: Builds for `linux/amd64` and `linux/arm64`.
- **Authentication**: Credentials are securely handled via inputs.

## Support

For issues, join here https://t.me/AeonDiscussion.


## License

This project is licensed under the MIT License. Refer to the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- Special thanks to the original developers of the [Mirror-Leech-Telegram-Bot](https://github.com/anasty17/mirror-leech-telegram-bot).
- Gratitude to contributors from various repositories whose features have been integrated into Aeon.


## Recent activity [![Time period](https://images.repography.com/58464391/AeonOrg/Aeon-MLTB/recent-activity/MUUzwqnoU_5n6kL3Jc8TTWcA3UxPyCHC2emNNSTGJh8/4gYNvj3-wi0i5zQVemeNAbqB7TrkUx_7BxZxhReSIVg_badge.svg)](https://repography.com)
[![Timeline graph](https://images.repography.com/58464391/AeonOrg/Aeon-MLTB/recent-activity/MUUzwqnoU_5n6kL3Jc8TTWcA3UxPyCHC2emNNSTGJh8/4gYNvj3-wi0i5zQVemeNAbqB7TrkUx_7BxZxhReSIVg_timeline.svg)](https://github.com/AeonOrg/Aeon-MLTB/commits)