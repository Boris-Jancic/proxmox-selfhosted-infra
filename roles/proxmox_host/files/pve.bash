# Managed by Ansible (roles/proxmox_host). Proxmox-aware prompt, login banner
# and guest helpers. Reads pmxcfs files (/etc/pve/.members, .vmlist, .rrd)
# directly instead of pvesh, so everything here is instant.

_C_RST=$'\e[0m' _C_DIM=$'\e[2m' _C_BOLD=$'\e[1m'
_C_RED=$'\e[1;31m' _C_GRN=$'\e[1;32m' _C_YLW=$'\e[1;33m' _C_BLU=$'\e[1;34m' _C_CYN=$'\e[36m'

# --- Data ---

# One line per guest, cluster-wide, sorted by ID:
#   id type node name status mem maxmem uptime
_pve_guests() {
  [ -r /etc/pve/.vmlist ] || return 1
  awk '
    FNR == NR {
      if (match($0, /"[0-9]+": *\{/)) {
        id = substr($0, RSTART + 1); sub(/".*/, "", id)
        n = $0; sub(/.*"node": *"/, "", n); sub(/".*/, "", n)
        t = $0; sub(/.*"type": *"/, "", t); sub(/".*/, "", t)
        node[id] = n; type[id] = t
      }
      next
    }
    $0 ~ /^pve[^\/]*-vm[^\/]*\// {
      split($0, f, ":"); id = f[1]; sub(/.*\//, "", id)
      up[id] = f[2]; name[id] = f[3]
      st[id] = (f[5] == 1) ? "template" : f[4]
      maxmem[id] = f[9]; mem[id] = f[10]
    }
    END {
      for (id in node)
        printf "%s %s %s %s %s %s %s %s\n", id, type[id], node[id],
          (id in name && name[id] != "") ? name[id] : "-",
          (id in st) ? st[id] : "unknown",
          mem[id] + 0, maxmem[id] + 0, up[id] + 0
    }
  ' /etc/pve/.vmlist /etc/pve/.rrd 2>/dev/null | sort -n
}

# Resolve an ID or name to "id type node name".
_pve_resolve() {
  _pve_guests | awk -v q="$1" '$1 == q || $4 == q { print $1, $2, $3, $4; exit }'
}

# Cluster node IP from .members (falls back to the name).
_pve_node_ip() {
  local ip
  ip=$(sed -n "s/.*\"$1\": *{[^}]*\"ip\": *\"\([^\"]*\)\".*/\1/p" /etc/pve/.members 2>/dev/null)
  echo "${ip:-$1}"
}

_pve_human() {  # bytes -> 1.2G
  awk -v b="$1" 'BEGIN { split("B K M G T", u); i = 1
    while (b >= 1024 && i < 5) { b /= 1024; i++ }
    printf (i > 2 ? "%.1f%s" : "%d%s"), b, u[i] }'
}

# --- Commands ---

# guests [filter] — cluster-wide guest table (filter matches any column).
guests() {
  local here; here=$(hostname)
  _pve_guests | awk -v here="$here" -v q="$1" \
    -v rst="$_C_RST" -v dim="$_C_DIM" -v bold="$_C_BOLD" \
    -v red="$_C_RED" -v grn="$_C_GRN" -v ylw="$_C_YLW" -v cyn="$_C_CYN" '
    function hum(b,  u, i) { split("B K M G T", u); i = 1
      while (b >= 1024 && i < 5) { b /= 1024; i++ }
      return sprintf(i > 2 ? "%.1f%s" : "%d%s", b, u[i]) }
    function dur(s) { return s >= 86400 ? int(s / 86400) "d" : s >= 3600 ? int(s / 3600) "h" : s > 0 ? int(s / 60) "m" : "-" }
    BEGIN { printf "%s%-5s %-4s %-22s %-11s %-9s %-13s %s%s\n", bold, "ID", "TYPE", "NAME", "NODE", "STATUS", "MEM", "UP", rst }
    q != "" && index($0, q) == 0 { next }
    {
      c = $5 == "running" ? grn : $5 == "stopped" ? red : ylw
      nc = $3 == here ? cyn : dim
      t = $2 == "qemu" ? "vm" : "ct"
      m = $5 == "running" ? hum($6) "/" hum($7) : "-"
      printf "%-5s %-4s %-22s %s%-11s%s %s%-9s%s %-13s %s\n", $1, t, $4, nc, $3, rst, c, $5, rst, m, dur($8)
    }'
}

# ct <id|name> — enter a container, over SSH if it lives on another node.
ct() {
  local id type node name
  [ -n "$1" ] || { echo "usage: ct <ctid|name>" >&2; return 2; }
  read -r id type node name < <(_pve_resolve "$1")
  [ "$type" = lxc ] || { echo "ct: no container '$1'" >&2; return 1; }
  if [ "$node" = "$(hostname)" ]; then
    pct enter "$id"
  else
    ssh -t "root@$(_pve_node_ip "$node")" pct enter "$id"
  fi
}

# gconf <id|name> — show a guest's config, wherever it lives.
gconf() {
  local id type node name dir
  [ -n "$1" ] || { echo "usage: gconf <vmid|name>" >&2; return 2; }
  read -r id type node name < <(_pve_resolve "$1")
  [ -n "$id" ] || { echo "gconf: no guest '$1'" >&2; return 1; }
  [ "$type" = qemu ] && dir=qemu-server || dir=lxc
  echo "${_C_DIM}# /etc/pve/nodes/$node/$dir/$id.conf  ($name)${_C_RST}"
  sed -E "s/^([a-z0-9_]+):/${_C_CYN}\1${_C_RST}:/; s/^(\[.*\])$/${_C_YLW}\1${_C_RST}/" \
    "/etc/pve/nodes/$node/$dir/$id.conf"
}

# pve-motd — node/cluster/storage/guest summary (shown at login).
pve-motd() {
  local here ver up load memu memt q cname l
  here=$(hostname)
  ver=$(dpkg-query -W -f='${Version}' pve-manager 2>/dev/null)
  up=$(uptime -p | sed 's/^up //')
  read -r load _ < /proc/loadavg
  read -r memt memu < <(command free -b | awk '/^Mem:/ { print $2, $3 }')

  echo
  echo " ${_C_BOLD}${_C_YLW}$here${_C_RST}  ${_C_DIM}pve-manager $ver · kernel $(uname -r)${_C_RST}"
  echo " ${_C_DIM}up${_C_RST} $up  ${_C_DIM}load${_C_RST} $load  ${_C_DIM}mem${_C_RST} $(_pve_human "$memu")/$(_pve_human "$memt")"

  # Cluster + node status
  if [ -r /etc/pve/.members ]; then
    l=$(grep -m1 '"cluster"' /etc/pve/.members)
    if [ -n "$l" ]; then
      cname=${l#*\"name\": \"}; cname=${cname%%\"*}
      q=${l#*\"quorate\": }; q=${q%% *}
      printf ' %scluster%s %s%s%s ' "$_C_DIM" "$_C_RST" "$_C_BOLD" "$cname" "$_C_RST"
      [ "$q" = 1 ] && printf '%squorate%s  ' "$_C_GRN" "$_C_RST" || printf '%sNO QUORUM%s  ' "$_C_RED" "$_C_RST"
      sed -n 's/.*"\([^"]*\)": { "id": [0-9]*, "online": \([01]\).*/\1 \2/p' /etc/pve/.members |
        while read -r n on; do
          [ "$on" = 1 ] && printf '%s●%s %s  ' "$_C_GRN" "$_C_RST" "$n" || printf '%s●%s %s  ' "$_C_RED" "$_C_RST" "$n"
        done
      echo
    fi
  fi

  # Filesystems + LVM thin pools (red at >=85%)
  printf ' %sdisk%s ' "$_C_DIM" "$_C_RST"
  { command df -B1 --output=target,pcent,size "${PVE_MOTD_MOUNTS[@]}" 2>/dev/null | tail -n +2 | awk '{ print $1, $2+0, $3 }'
    lvs --noheadings --nosuffix --units b -o vg_name,lv_name,data_percent,lv_size -S 'lv_attr=~^t' 2>/dev/null |
      awk '{ print $1 "/" $2, int($3), $4 }'
  } | while read -r what pct size; do
    [ "$pct" -ge 85 ] && c=$_C_RED || { [ "$pct" -ge 70 ] && c=$_C_YLW || c=$_C_GRN; }
    printf '%s %s%s%%%s/%s  ' "$what" "$c" "$pct" "$_C_RST" "$(_pve_human "$size")"
  done
  echo

  # Guests
  echo
  guests
  echo
  echo " ${_C_DIM}guests [filter] · ct <id|name> · gconf <id|name> · pvests · pvelog · pvetasks${HOMELAB_REPO:+ · ap <playbook>}${_C_RST}"
  echo
}

# Mounts shown in the banner (missing ones are skipped).
PVE_MOTD_MOUNTS=(/ /mnt/backups)

# --- Aliases ---
alias pvests='systemctl --no-pager list-units "pve*" corosync.service --type=service --all'
alias pvelog='journalctl -f -n 50 -u pvedaemon -u pveproxy -u pvestatd -u pve-cluster -u corosync'
alias pvetasks='pvenode task list --limit 20'

# ap <playbook> [args] — ansible-playbook from the homelab repo.
if [ -d "$HOMELAB_REPO/playbooks" ]; then
  # Bare names resolve to playbooks/: `ap site --tags caddy`.
  ap() {
    local pb=$1; shift
    (cd "$HOMELAB_REPO" || exit
     [ -f "$pb" ] || for c in "playbooks/$pb" "playbooks/$pb.yml"; do [ -f "$c" ] && pb=$c && break; done
     ansible-playbook "$pb" "$@")
  }
  _ap_complete() {
    local cur=${COMP_WORDS[COMP_CWORD]}
    if [[ $cur == -* ]]; then
      COMPREPLY=($(compgen -W '--tags --skip-tags --limit --check --diff --list-tasks --list-tags --ask-vault-pass --start-at-task -v -vv -vvv' -- "$cur"))
    else
      COMPREPLY=($(compgen -W "$(cd "$HOMELAB_REPO/playbooks" && ls *.yml)" -- "$cur"))
    fi
  }
  complete -F _ap_complete ap
fi

# --- Completion ---
_pve_complete_guests() {  # $1: lxc|qemu|all
  local cur=${COMP_WORDS[COMP_CWORD]}
  COMPREPLY=($(compgen -W "$(_pve_guests | awk -v t="$1" 't == "all" || $2 == t { print $1; if ($4 != "-") print $4 }')" -- "$cur"))
}
_pve_complete_ct() { _pve_complete_guests lxc; }
_pve_complete_all() { _pve_complete_guests all; }
complete -F _pve_complete_ct ct
complete -F _pve_complete_all gconf

# --- Prompt ---
[ -r /usr/lib/git-core/git-sh-prompt ] && . /usr/lib/git-core/git-sh-prompt
GIT_PS1_SHOWDIRTYSTATE=1 GIT_PS1_SHOWUNTRACKEDFILES=1

_pve_prompt() {
  local rc=$? l cname q p
  local R='\[\e[0m\]' RED='\[\e[1;31m\]' GRN='\[\e[1;32m\]' YLW='\[\e[1;33m\]' BLU='\[\e[1;34m\]' CYN='\[\e[36m\]' MAG='\[\e[35m\]'

  p='\[\e]0;\u@\h: \w\a\]'"${RED}\u${R}@${YLW}\h${R}"
  # Cluster badge: green when quorate, red otherwise (builtin read, no fork).
  if [ -r /etc/pve/.members ]; then
    while IFS= read -r l; do
      case $l in *'"cluster"'*)
        cname=${l#*\"name\": \"}; cname=${cname%%\"*}
        q=${l#*\"quorate\": }; q=${q%% *}
        [ "$q" = 1 ] && p+=" ${GRN}⬢ $cname${R}" || p+=" ${RED}⬢ $cname NO QUORUM${R}"
        break ;;
      esac
    done < /etc/pve/.members
  fi
  p+=" ${BLU}\w${R}"
  declare -F __git_ps1 >/dev/null && p+="${MAG}$(__git_ps1 ' (%s)')${R}"
  [ -n "$VIRTUAL_ENV" ] && p+=" ${CYN}(${VIRTUAL_ENV##*/})${R}"
  [ "$rc" != 0 ] && p+=" ${RED}✘ $rc${R}"
  PS1="$p\n${RED}\\\$${R} "
}
PROMPT_COMMAND="_pve_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

# --- Login banner: top-level interactive TTY shells only ---
if [ -t 1 ] && [ "${SHLVL:-1}" -le 1 ] && [ -z "$CLAUDECODE" ]; then
  pve-motd
fi
