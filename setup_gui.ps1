Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = "MaiBot 部署向导"
$form.Size = New-Object System.Drawing.Size(520, 400)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = "MaiBot 微信 AI 机器人 - 快速部署"
$title.Font = New-Object System.Drawing.Font("Microsoft YaHei", 14, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(30, 20)
$form.Controls.Add($title)

$stepLabel = New-Object System.Windows.Forms.Label
$stepLabel.Text = "请输入以下信息完成部署："
$stepLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei", 10)
$stepLabel.AutoSize = $true
$stepLabel.Location = New-Object System.Drawing.Point(30, 60)
$form.Controls.Add($stepLabel)

# DeepSeek Key
$keyLabel = New-Object System.Windows.Forms.Label
$keyLabel.Text = "① DeepSeek API Key"
$keyLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei", 10)
$keyLabel.AutoSize = $true
$keyLabel.Location = New-Object System.Drawing.Point(30, 100)
$form.Controls.Add($keyLabel)

$keyLink = New-Object System.Windows.Forms.LinkLabel
$keyLink.Text = " 注册获取 →"
$keyLink.Font = New-Object System.Drawing.Font("Microsoft YaHei", 9)
$keyLink.AutoSize = $true
$keyLink.Location = New-Object System.Drawing.Point(180, 101)
$keyLink.LinkColor = "Blue"
$keyLink.Add_Click({ [System.Diagnostics.Process]::Start("https://platform.deepseek.com") })
$form.Controls.Add($keyLink)

$keyInput = New-Object System.Windows.Forms.TextBox
$keyInput.Size = New-Object System.Drawing.Size(440, 25)
$keyInput.Location = New-Object System.Drawing.Point(30, 130)
$keyInput.Font = New-Object System.Drawing.Font("Consolas", 10)
$form.Controls.Add($keyInput)

# WeChat Name
$nameLabel = New-Object System.Windows.Forms.Label
$nameLabel.Text = "② 微信昵称（窗口顶部的名字）"
$nameLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei", 10)
$nameLabel.AutoSize = $true
$nameLabel.Location = New-Object System.Drawing.Point(30, 175)
$form.Controls.Add($nameLabel)

$nameInput = New-Object System.Windows.Forms.TextBox
$nameInput.Size = New-Object System.Drawing.Size(440, 25)
$nameInput.Location = New-Object System.Drawing.Point(30, 205)
$nameInput.Font = New-Object System.Drawing.Font("Microsoft YaHei", 10)
$form.Controls.Add($nameInput)

# Status
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "就绪"
$statusLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei", 9)
$statusLabel.ForeColor = "Gray"
$statusLabel.AutoSize = $true
$statusLabel.Location = New-Object System.Drawing.Point(30, 250)
$form.Controls.Add($statusLabel)

# Progress bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Size = New-Object System.Drawing.Size(440, 20)
$progressBar.Location = New-Object System.Drawing.Point(30, 275)
$progressBar.Visible = $false
$form.Controls.Add($progressBar)

function Update-Status {
    param($text)
    $statusLabel.Text = $text
    $statusLabel.Refresh()
}

# Deploy button
$deployBtn = New-Object System.Windows.Forms.Button
$deployBtn.Text = "开始部署"
$deployBtn.Size = New-Object System.Drawing.Size(120, 35)
$deployBtn.Location = New-Object System.Drawing.Point(190, 310)
$deployBtn.Font = New-Object System.Drawing.Font("Microsoft YaHei", 10)
$form.Controls.Add($deployBtn)

$deployBtn.Add_Click({
    $key = $keyInput.Text.Trim()
    $name = $nameInput.Text.Trim()
    
    if (-not $key) { [System.Windows.Forms.MessageBox]::Show("请输入 DeepSeek API Key", "提示"); return }
    if (-not $name) { [System.Windows.Forms.MessageBox]::Show("请输入微信昵称", "提示"); return }
    
    $deployBtn.Enabled = $false
    $progressBar.Visible = $true
    $progressBar.Value = 10
    
    # Step 1: Install deps
    Update-Status "[1/4] 安装依赖..."
    $progressBar.Value = 20
    Start-Process -Wait -NoNewWindow python "-m pip install -r requirements.txt -q"
    Start-Process -Wait -NoNewWindow python "-m pip install wxauto -q"
    
    # Step 2: Generate config
    Update-Status "[2/4] 生成配置文件..."
    $progressBar.Value = 40
    Start-Process -Wait -NoNewWindow python "tools/setup_config.py `"$name`" `"$key`""
    
    # Step 3: Create dirs
    Update-Status "[3/4] 创建数据目录..."
    $progressBar.Value = 60
    if (-not (Test-Path "data/emoji")) { New-Item -ItemType Directory -Path "data/emoji" -Force | Out-Null }
    if (-not (Test-Path "data/images")) { New-Item -ItemType Directory -Path "data/images" -Force | Out-Null }
    
    # Step 4: Done
    Update-Status "[4/4] 部署完成！"
    $progressBar.Value = 100
    
    [System.Windows.Forms.MessageBox]::Show("部署完成！`n`n微信昵称: $name`nAPI Key: $($key.Substring(0,10))...`n`n双击 start.bat 启动机器人", "完成", "OK", "Information")
    
    $deployBtn.Enabled = $true
})

[System.Windows.Forms.Application]::Run($form)
