# Define shell functions facilitating app deployment.
#
# Usage
#     % source INIT.sh
#     % DEPLOY
#
# Notes
# 1.  The --quiet option (also, -q) for the gcloud CLI disables all 
#     interactive prompts when running gcloud CLI commands and is useful 
#     for scripting. If input is needed, defaults are used. If there 
#     isn't a default, an error is raised.
#
# 2.  Use zsh setopt SH_WORD_SPLIT to enable traditional parameter 
#     expansion.  Why "2> /dev/null || true"?  Because bash doesn't have 
#     a setopt command.

ERROR () { printf "ERROR: %s\n" "$*" >& 2; }


VERSIONS_DELETE () {
    local IDS=""
    gcloud app versions list |
    while read SERVICE VERSION_ID TRAFFIC_SPLIT RESIDUE; do
        case "$SERVICE $TRAFFIC_SPLIT" in
            "default 0.00")  IDS="$IDS $VERSION_ID";;
        esac
    done

    (
        setopt SH_WORD_SPLIT 2> /dev/null || true
        set -x; gcloud app versions delete --quiet $IDS
    )
}


DEPLOY () {
    # deploy app (without confirmation prompt)
    (set -x; gcloud app deploy --quiet)

    # delete old versions (without confirmation prompt)
    VERSIONS_DELETE  

    # stream logs
    (set -x; gcloud app logs tail -s default)
    }

return
# if return failed, then this script is being run instead of sourced.
ERROR "This script should be sourced, not run."
exit 1
