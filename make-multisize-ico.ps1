param(
  [Parameter(Mandatory=$true)] [string]$Input,
  [Parameter(Mandatory=$true)] [string]$Output,
  [int[]]$Sizes = @(16,20,24,32,40,48,64,128,256)
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Input))  { throw "Parameter -Input ist leer." }
if ([string]::IsNullOrWhiteSpace($Output)) { throw "Parameter -Output ist leer." }
if (-not (Test-Path -LiteralPath $Input))  { throw "Input nicht gefunden: $Input" }

Add-Type -AssemblyName System.Drawing

function Get-BaseBitmapFromIco {
  param([byte[]]$Bytes)
  $ms = [System.IO.MemoryStream]::new($Bytes)
  $br = [System.IO.BinaryReader]::new($ms)
  $reserved = $br.ReadUInt16(); $type=$br.ReadUInt16(); $count=$br.ReadUInt16()
  if ($reserved -ne 0 -or $type -ne 1 -or $count -lt 1) { throw "Ungültiges ICO." }
  $entries = @()
  for ($i=0; $i -lt $count; $i++) {
    $w=$br.ReadByte(); if ($w -eq 0){$w=256}; $h=$br.ReadByte(); if ($h -eq 0){$h=256}
    [void]$br.ReadByte(); [void]$br.ReadByte()
    $planes=$br.ReadUInt16(); $bits=$br.ReadUInt16()
    $size=$br.ReadUInt32(); $off=$br.ReadUInt32()
    $entries += [pscustomobject]@{W=$w;H=$h;Size=$size;Off=$off}
  }
  $best = $entries | Sort-Object { $_.W * $_.H } -Descending | Select-Object -First 1
  $ms.Position = $best.Off
  $imgBytes = $br.ReadBytes([int]$best.Size)
  $imgStream = [System.IO.MemoryStream]::new($imgBytes)
  [System.Drawing.Image]::FromStream($imgStream, $true, $true)
}

function Get-BaseBitmap {
  param([string]$Path)
  switch ([IO.Path]::GetExtension($Path).ToLowerInvariant()) {
    ".ico" { Get-BaseBitmapFromIco ([IO.File]::ReadAllBytes($Path)) }
    default { [System.Drawing.Image]::FromFile($Path) }
  }
}

function New-ResizedBitmap {
  param([System.Drawing.Image]$Src, [int]$Size)
  $bmp = New-Object System.Drawing.Bitmap($Size,$Size,[System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.CompositingQuality=[System.Drawing.Drawing2D.CompositingQuality]::HighQuality
  $g.PixelOffsetMode=[System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.Clear([System.Drawing.Color]::Transparent)
  $min=[double][Math]::Min($Src.Width,$Src.Height)
  $sx=($Src.Width-$min)/2.0; $sy=($Src.Height-$min)/2.0
  $srcRect=New-Object System.Drawing.RectangleF($sx,$sy,$min,$min)
  $dstRect=New-Object System.Drawing.Rectangle(0,0,$Size,$Size)
  $g.DrawImage($Src,$dstRect,$srcRect,[System.Drawing.GraphicsUnit]::Pixel)
  $g.Dispose(); return $bmp
}

function Get-PngBytes { param([System.Drawing.Image]$Img)
  $ms=[IO.MemoryStream]::new(); $Img.Save($ms,[System.Drawing.Imaging.ImageFormat]::Png)
  $b=$ms.ToArray(); $ms.Dispose(); return $b
}

function Write-Ico {
  param([string]$Path,[byte[][]]$Images,[int[]]$Widths,[int[]]$Heights)
  $fs=[IO.File]::Open($Path,[IO.FileMode]::Create,[IO.FileAccess]::Write)
  $bw=[IO.BinaryWriter]::new($fs)
  $count=$Images.Count
  $bw.Write([UInt16]0); $bw.Write([UInt16]1); $bw.Write([UInt16]$count)
  $dirStart=$fs.Position; $bw.Write((New-Object byte[](16*$count)))
  $offsets=@()
  foreach ($img in $Images){ $offsets+= $fs.Position; $bw.Write($img) }
  $fs.Position=$dirStart; $current=6+(16*$count)
  for ($i=0;$i -lt $count;$i++) {
    $w=$Widths[$i]; $h=$Heights[$i]
    $wb=[byte]($w -band 0xFF); if($w -ge 256){$wb=0}
    $hb=[byte]($h -band 0xFF); if($h -ge 256){$hb=0}
    $bw.Write($wb); $bw.Write($hb); $bw.Write([byte]0); $bw.Write([byte]0)
    $bw.Write([UInt16]1); $bw.Write([UInt16]32)
    $bw.Write([UInt32]$Images[$i].Length)
    $bw.Write([UInt32]$current)
    $current += $Images[$i].Length
  }
  $bw.Flush(); $bw.Dispose(); $fs.Dispose()
}

# --- Workflow ---
$src = Get-BaseBitmap -Path $Input
$Sizes = ($Sizes | Sort-Object -Unique) | Where-Object { $_ -gt 0 }

$pngs = New-Object 'System.Collections.Generic.List[byte[]]'
$ws   = New-Object 'System.Collections.Generic.List[int]'
$hs   = New-Object 'System.Collections.Generic.List[int]'

foreach ($s in $Sizes) { $bmp = New-ResizedBitmap $src $s; $pngs.Add((Get-PngBytes $bmp)); $ws.Add($s); $hs.Add($s); $bmp.Dispose() }
$src.Dispose()

# Zielordner (auch wenn Datei noch nicht existiert)
$fullOut = [IO.Path]::GetFullPath($Output)
$dstDir  = [IO.Path]::GetDirectoryName($fullOut)
if (-not [string]::IsNullOrWhiteSpace($dstDir) -and -not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }

Write-Ico -Path $fullOut -Images $pngs.ToArray() -Widths $ws.ToArray() -Heights $hs.ToArray()
Write-Host "OK: Multi-Size-ICO geschrieben → $fullOut" -ForegroundColor Green
